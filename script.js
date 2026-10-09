// 粤乡智匠 — 功能模块（依赖 js/core.js）

// ==================== 初始化 ====================

document.addEventListener('DOMContentLoaded', function() {
    fixIOSViewport();
    initializeApp();
    registerServiceWorker();
});

function initializeApp() {
    // 首屏不再无条件弹「点击了解项目功能」这种语义不明、无指向的 toast；
    // 首次访问的引导由 checkOnboarding() 的引导层负责。
    checkOnboarding();
    const setupFns = [
        setupNavigation, setupLoginModal,
        setupProductSelection, setupCraftSelection, setupDialectSelection,
        setupVoiceInput, setupAgricultureQA, setupCalendar,
        setupPestDiagnosisEntry, setupEventListeners, setupUserDropdown,
        setupCaseButtons, setupEmploymentTab, setupPolicySection,
        setupTeacherPanel, setup3DControls, setupQuickMessage,
        restoreSession, checkConnection, setupScrollReveal,
        setupNavbarScroll, setupHeroParticles, setupStatCounter,
        setupSmoothScroll, setupThemeToggle, setupLargeTextToggle, setupHamburger,
        updateCraftSteps, setupPestGuide
    ];
    setupFns.forEach(fn => {
        try { fn(); } catch(e) { console.error(`${fn.name} 初始化失败:`, e); }
    });
}

// ==================== 主题切换 ====================

function setupThemeToggle() {
    const btn = document.getElementById('theme-toggle');
    if (!btn) return;
    // 恢复保存的主题
    const saved = localStorage.getItem(STORAGE_KEYS.THEME);
    if (saved) {
        document.documentElement.dataset.theme = saved;
        updateThemeIcon(saved);
    }
    btn.addEventListener('click', toggleTheme);
}

function toggleTheme() {
    const current = document.documentElement.dataset.theme;
    const next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.theme = next;
    localStorage.setItem(STORAGE_KEYS.THEME, next);
    updateThemeIcon(next);
}

function updateThemeIcon(theme) {
    const btn = document.getElementById('theme-toggle');
    if (!btn) return;
    const icon = btn.querySelector('i');
    if (icon) {
        icon.className = theme === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
    }
}

// ==================== 大字模式（无障碍） ====================
// 顶部「大字模式」按钮此前是死控件：styles.css 里 html[data-large-text] 的规则齐全，
// 但没有任何 JS 去切换这个属性。这里把它接上，并持久化到 localStorage。

function setupLargeTextToggle() {
    const btn = document.getElementById('large-text-toggle');
    if (!btn) return;
    let saved = false;
    try { saved = localStorage.getItem(STORAGE_KEYS.LARGE_TEXT) === '1'; } catch (e) { /* 隐私模式忽略 */ }
    applyLargeText(saved);
    btn.addEventListener('click', () => {
        const next = document.documentElement.dataset.largeText !== '1';
        applyLargeText(next);
        try { localStorage.setItem(STORAGE_KEYS.LARGE_TEXT, next ? '1' : '0'); } catch (e) { /* 隐私模式忽略 */ }
    });
}

function applyLargeText(on) {
    const root = document.documentElement;
    if (on) {
        root.dataset.largeText = '1';
    } else {
        delete root.dataset.largeText;
    }
    const btn = document.getElementById('large-text-toggle');
    if (btn) btn.setAttribute('aria-pressed', on ? 'true' : 'false');
}

// ==================== 汉堡菜单 ====================

function setupHamburger() {
    const btn = document.getElementById('hamburger-btn');
    const menu = document.getElementById('nav-menu');
    if (!btn || !menu) return;

    btn.addEventListener('click', () => {
        const isOpen = menu.classList.toggle('open');
        btn.classList.toggle('open');
        btn.setAttribute('aria-expanded', isOpen);
    });

    menu.addEventListener('click', (e) => {
        if (e.target.classList.contains('nav-item')) {
            menu.classList.remove('open');
            btn.classList.remove('open');
            btn.setAttribute('aria-expanded', 'false');
        }
    });

    document.addEventListener('click', (e) => {
        if (!menu.contains(e.target) && !btn.contains(e.target)) {
            menu.classList.remove('open');
            btn.classList.remove('open');
            btn.setAttribute('aria-expanded', 'false');
        }
    });
}

// ==================== 会话恢复 ====================

/* 统一 user 对象口径：id 缺失时回落到 user_id。
   历史原因：老版 /api/auth/verify 直接回了 database.get_session() 的结果
   （{user_id, name, role}，没有 id），restoreSession() 把它整体覆盖到
   AppState.user 上，于是 AppState.user.id === undefined，
   所有 `/api/xxx/${AppState.user.id}` 都会被拼成 `/api/xxx/undefined`
   （就业对接的 _self_only 会因此返回 403）。
   后端已修，这里再兜一层：服务端没重启时（新前端 + 旧后端）也不会退化。 */
function normalizeUser(u) {
    if (!u || typeof u !== 'object') return u;
    const id = u.id || u.user_id || '';
    if (u.id === id) return u;
    return Object.assign({}, u, { id });
}

function restoreSession() {
    const saved = localStorage.getItem(STORAGE_KEYS.SESSION);
    if (!saved) return;
    try {
        const parsed = JSON.parse(saved);
        const sessionId = parsed.sessionId;
        AppState.sessionId = sessionId;
        AppState.user = normalizeUser(parsed.user);
        apiCall('/api/auth/verify', 'POST', { session_id: sessionId })
            .then(data => {
                if (data.success) {
                    AppState.user = normalizeUser(Object.assign({}, AppState.user, data.user));
                    updateUserUI();
                    if (typeof onLoginSuccess === 'function') onLoginSuccess();
                    // P1-5：刷新页面恢复会话后也要拉一次积分（此前只在登录时拉，
                    // 刷新后积分余额恒为占位符，学员查不到自己有多少积分）。
                    loadUserData();
                    // 农事提醒补发（幂等，静默执行，不阻塞渲染）
                    checkFarmingReminders();
                    syncFarmingSubscriptionButton();
                } else {
                    localStorage.removeItem(STORAGE_KEYS.SESSION);
                }
            })
            .catch(() => {
                // 离线时仍用本地数据
                updateUserUI();
            });
    } catch(e) {
        localStorage.removeItem(STORAGE_KEYS.SESSION);
    }
}

// ==================== 导航 ====================

function setupNavigation() {
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', function() {
            switchTab(this.getAttribute('data-tab'));
        });
    });
    // 键盘左右箭头切换tab
    const navMenu = document.getElementById('nav-menu');
    if (navMenu) {
        navMenu.addEventListener('keydown', function(e) {
            const tabs = [...this.querySelectorAll('.nav-item')];
            const current = tabs.findIndex(t => t === document.activeElement);
            if (e.key === 'ArrowRight') {
                e.preventDefault();
                const next = (current + 1) % tabs.length;
                tabs[next].focus();
                tabs[next].click();
            } else if (e.key === 'ArrowLeft') {
                e.preventDefault();
                const prev = (current - 1 + tabs.length) % tabs.length;
                tabs[prev].focus();
                tabs[prev].click();
            }
        });
    }
    // Escape关闭模态框
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            const detailModal = document.querySelector('.modal-overlay.detail-modal');
            if (detailModal) { detailModal.remove(); return; }
            const loginModal = document.getElementById('login-modal');
            if (loginModal && !loginModal.classList.contains('is-hidden')) {
                loginModal.classList.add('is-hidden');
            }
        }
    });
}

function switchTab(tabName) {
    // ===== 权限守卫 =====
    if (AppState.user && !isTabAllowed(tabName, AppState.user.role)) {
        showNotification("无权访问该页面", "error");
        tabName = ROLE_DEFAULT[AppState.user.role] || "agriculture";
    }
    // ===== 离场清理 =====
    // 切走「电商运营」时必须停掉直播间（朗读计时 + 语音识别 + 各刷新定时器），
    // 否则定时器在后台空转、麦克风被占用到刷新页面。
    if (AppState.currentTab === 'ecommerce' && tabName !== 'ecommerce'
        && typeof stopLiveSimulation === 'function') {
        stopLiveSimulation();
    }
    // 更新导航栏active + ARIA
    document.querySelectorAll('.nav-item').forEach(item => {
        const isActive = item.getAttribute('data-tab') === tabName;
        item.classList.toggle('active', isActive);
        item.setAttribute('aria-selected', isActive);
    });
    // 淡出当前tab
    const allTabs = document.querySelectorAll('.tab-content');
    const currentActive = document.querySelector('.tab-content.active');
    if (currentActive) {
        currentActive.style.opacity = '0';
        currentActive.style.transform = 'translateY(12px)';
    }
    setTimeout(() => {
        allTabs.forEach(c => c.classList.remove('active'));
        const target = document.getElementById(tabName + '-tab');
        if (target) {
            target.classList.add('active');
            target.style.opacity = '0';
            target.style.transform = 'translateY(12px)';
            requestAnimationFrame(() => {
                target.style.opacity = '1';
                target.style.transform = 'translateY(0)';
            });
            AppState.currentTab = tabName;
            // 滚动到主内容区，让用户看到切换后的板块
            document.getElementById('main-content')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
        // 更新面包屑
        const tabNames = {
            agriculture: '农业技能', ecommerce: '电商运营', crafts: '手工传承',
            resources: '本土资源', employment: '就业对接',
            teacher: '教师管理', admin: '系统管理', government: '政府工作台',
            enterprise: '企业中心', discussions: '讨论社区'
        };
        const breadcrumb = document.getElementById('breadcrumb-current');
        const breadcrumbBar = document.getElementById('breadcrumb-bar');
        if (breadcrumb && tabNames[tabName]) {
            breadcrumb.textContent = tabNames[tabName];
            breadcrumbBar?.classList.add('visible');
        }
        // 切到教师tab时加载数据
        if (tabName === 'teacher') loadTeacherDashboard();
        // 切到就业tab时刷新数据
        if (tabName === 'employment') loadEmploymentData();
        // 新面板数据加载
        if (tabName === 'government') loadGovDashboard();
        if (tabName === 'enterprise') loadEnterpriseJobs();
        if (tabName === 'discussions') loadDiscussions();
        // P4（2026-10-06）：切到手工传承时轻量重拉 3D 模型，让教师新发布的模型及时可见。
        if (tabName === 'crafts') loadCraftModels();
        // 切到本土资源时加载本地成功案例与政策（首次加载后缓存，除非显式 force）
        if (tabName === 'resources') {
            loadSuccessCases();
            loadPolicies();
        }
    }, 200);
}

// ==================== 焦点捕获 ====================

function trapFocus(modal) {
    const focusable = modal.querySelectorAll(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    );
    if (focusable.length === 0) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    modal.addEventListener('keydown', function(e) {
        if (e.key === 'Tab') {
            if (e.shiftKey && document.activeElement === first) {
                e.preventDefault();
                last.focus();
            } else if (!e.shiftKey && document.activeElement === last) {
                e.preventDefault();
                first.focus();
            }
        }
    });
    first?.focus();
}

// ==================== 登录 ====================

function setupLoginModal() {
    const loginBtn = document.getElementById('login-btn');
    const loginModal = document.getElementById('login-modal');
    const closeBtn = document.getElementById('close-login-modal');
    const submitBtn = document.getElementById('login-submit');
    const demoBtn = document.getElementById('demo-login');
    const logoutBtn = document.getElementById('logout-btn');

    loginBtn?.addEventListener('click', () => {
        loginModal.classList.remove('is-hidden');
        resetAuthTabs();
        trapFocus(loginModal);
    });
    closeBtn?.addEventListener('click', () => {
        loginModal.classList.add('is-hidden');
        resetAuthTabs();
    });
    submitBtn?.addEventListener('click', handleLogin);
    demoBtn?.addEventListener('click', handleDemoLogin);
    logoutBtn?.addEventListener('click', handleLogout);

    // 演示账户点击填充
    document.querySelectorAll('.demo-account').forEach(el => {
        el.addEventListener('click', function() {
            document.getElementById('login-username').value = this.dataset.username;
            document.getElementById('login-password').value = this.dataset.password;
        });
    });

    // 回车登录
    document.getElementById('login-password')?.addEventListener('keydown', e => {
        if (e.key === 'Enter') handleLogin();
    });
}

async function handleLogin() {
    const username = document.getElementById('login-username').value.trim();
    const password = document.getElementById('login-password').value;
    if (!username || !password) {
        showNotification('请输入用户名和密码', 'error');
        return;
    }
    showLoading('正在登录...');
    try {
        const data = await apiCall('/api/auth/login', 'POST', { username, password });
        hideLoading();
        if (data.success) {
            AppState.sessionId = data.session_id;
            AppState.user = normalizeUser(data.user);
            localStorage.setItem(STORAGE_KEYS.SESSION, JSON.stringify({
                sessionId: data.session_id,
                user: data.user
            }));
            document.getElementById('login-modal').classList.add('is-hidden');
            // 角色分流：跳转到独立门户
            var _role = data.user.role;
            if (_role === 'super_admin') { location.href = 'admin.html'; return; }
            if (_role === 'government') { location.href = 'government.html'; return; }
            if (_role === 'enterprise') { location.href = 'enterprise.html'; return; }
            if (_role === 'teacher') { location.href = 'teacher.html'; return; }
            updateUserUI();
            showNotification(`欢迎回来，${data.user.name}！`, 'success');
            loadUserData();
            if (typeof onLoginSuccess === 'function') onLoginSuccess();
        } else {
            showNotification(data.message || '登录失败', 'error');
        }
    } catch(e) {
        hideLoading();
        showNotification('连接服务器失败', 'error');
    }
}

function handleDemoLogin() {
    document.getElementById('login-username').value = 'student_demo';
    document.getElementById('login-password').value = '123456';
    handleLogin();
}

async function handleLogout() {
    apiCall("/api/auth/logout", "POST", { session_id: AppState.sessionId });
    AppState.sessionId = null;
    AppState.user = null;
    // 求职相关的用户态缓存必须一并清空，否则换个账号登录会看到上一个人的意向/简历状态
    MY_INTENT_KEYS = null;
    RESUME_CACHE = { profile: null, resume: null };
    localStorage.removeItem(STORAGE_KEYS.SESSION);
    resetToPublicView();
    showNotification("已退出登录", "info");
}

function updateUserUI() {
    if (!AppState.user) return;
    document.getElementById('login-section').classList.add('is-hidden');
    document.getElementById('user-info').classList.remove('is-hidden');
    document.getElementById('user-name').textContent = AppState.user.name;
    document.getElementById('user-role').textContent = AppState.user.role === 'teacher' ? '教师' : '学员';
    document.getElementById('dropdown-name').textContent = AppState.user.name;
    document.getElementById('dropdown-email').textContent = AppState.user.id;

    if (AppState.user.role === 'teacher') {
        document.querySelectorAll('.teacher-only').forEach(el => el.classList.remove('is-hidden'));
    } else {
        document.querySelectorAll('.teacher-only').forEach(el => el.classList.add('is-hidden'));
    }
    // 消息中心（铃铛）：所有**已登录**角色都可见（2026-10-07 修正）。
    // 容器 id 叫 teacher-quick-menu，但里面装的只有消息中心（公告推送 / 作业批改 /
    // 企业投递状态 / 互动私信），对学员同样相关 —— 此前只对教师显示，
    // 学员登录后根本看不到消息中心，红点修好了也没人能看见。
    // 未登录时的隐藏由初始 HTML 的 is-hidden 与 resetToPublicView() 负责。
    document.getElementById('teacher-quick-menu').classList.remove('is-hidden');
    // 「写消息」只对教师开放：收件人只有教师名册，学员/企业没有可主动发起的联系人。
    // 放在这里统一控制，避免出现一个点了只能说「暂不支持」的死按钮。
    const composeBtn = document.getElementById('msg-compose-btn');
    if (composeBtn) composeBtn.classList.toggle('is-hidden', AppState.user.role !== 'teacher');
}

async function loadUserData() {
    if (!AppState.user) return;
    try {
        const ptsData = await apiCall(`/api/employment/points/${AppState.user.id}`);
        if (ptsData.success) {
            const el = document.getElementById('points-balance');
            if (el) el.textContent = ptsData.points.toLocaleString();
        }
    } catch(e) {
        showNotification('加载积分数据失败', 'error');
    }
    // 加载就业模块数据
    loadEmploymentData();
}

// ==================== 用户下拉菜单 ====================

function setupUserDropdown() {
    const trigger = document.getElementById('user-dropdown-trigger');
    const menu = document.getElementById('user-dropdown-menu');
    if (!trigger || !menu) return;

    trigger.addEventListener('click', e => {
        e.stopPropagation();
        menu.classList.toggle('is-hidden');
    });

    document.addEventListener('click', () => menu.classList.add('is-hidden'));

    document.getElementById('profile-settings')?.addEventListener('click', e => {
        e.preventDefault();
        menu.classList.add('is-hidden');
        showSettingsModal();
    });
    document.getElementById('teaching-dashboard')?.addEventListener('click', e => {
        e.preventDefault();
        switchTab('teacher');
        menu.classList.add('is-hidden');
    });
    document.getElementById('help-center')?.addEventListener('click', e => {
        e.preventDefault();
        showNotification('帮助中心：使用顶部导航切换功能模块', 'info');
    });
}

// ==================== 个人设置（仿微信） ====================

// 消息通知偏好：控制是否在消息中心接收「教师 / 企业 / 超级管理员」发布的系统公告。
// 关闭后消息中心不再拉取通知源、红点也不显示；用户可随时在设置中重新开启。
function isNotifEnabled() {
    try { return localStorage.getItem(STORAGE_KEYS.NOTIF) !== '0'; } catch (e) { return true; }
}

function setNotifEnabled(on) {
    try { localStorage.setItem(STORAGE_KEYS.NOTIF, on ? '1' : '0'); } catch (e) { /* 隐私模式忽略 */ }
}

async function showSettingsModal() {
    const user = AppState.user || {};
    let profileData = null;
    try {
        const data = await apiCall('/api/user/profile');
        if (data.success) profileData = data.user;
    } catch(e) { console.warn('[个人设置] 资料加载失败，改用本地会话数据', e); }

    const name = profileData?.name || user.name || '';
    const email = profileData?.email || user.email || '';
    const username = profileData?.username || user.id || '';
    const role = profileData?.role || user.role || '';
    const createdAt = profileData?.created_at || '';
    const roleLabel = role === 'teacher' ? '教师' : '学员';
    const isDark = document.documentElement.dataset.theme === 'dark';

    showDetailModal('', `
        <div class="wx-settings">
            <!-- 个人信息卡片 -->
            <div class="wx-profile-card" id="wx-profile-card">
                <div class="wx-avatar">
                    <i class="fas fa-user"></i>
                </div>
                <div class="wx-profile-info">
                    <span class="wx-profile-name">${name}</span>
                    <span class="wx-profile-id">账号：${username}</span>
                </div>
                <i class="fas fa-chevron-right wx-chevron"></i>
            </div>

            <!-- 功能列表组1 -->
            <div class="wx-cell-group">
                <div class="wx-cell" id="wx-cell-my-posts">
                    <div class="wx-cell-icon"><i class="fas fa-bullhorn"></i></div>
                    <span class="wx-cell-label">通知公告</span>
                    <span class="wx-cell-value"></span>
                    <i class="fas fa-chevron-right wx-cell-arrow"></i>
                </div>
            </div>

            <!-- 功能列表组2 -->
            <div class="wx-cell-group">
                <div class="wx-cell" id="wx-cell-notifications">
                    <div class="wx-cell-icon blue"><i class="fas fa-bell"></i></div>
                    <span class="wx-cell-label">新消息通知</span>
                    <span class="wx-cell-value"></span>
                    <label class="wx-switch">
                        <input type="checkbox" id="wx-notif-toggle" ${isNotifEnabled() ? 'checked' : ''}>
                        <span class="wx-switch-slider"></span>
                    </label>
                </div>
                <div class="wx-cell" id="wx-cell-appearance">
                    <div class="wx-cell-icon purple"><i class="fas fa-moon"></i></div>
                    <span class="wx-cell-label">深色模式</span>
                    <span class="wx-cell-value"></span>
                    <label class="wx-switch">
                        <input type="checkbox" id="wx-dark-toggle" ${isDark ? 'checked' : ''}>
                        <span class="wx-switch-slider"></span>
                    </label>
                </div>
            </div>

            <!-- 功能列表组3 -->
            <div class="wx-cell-group">
                <div class="wx-cell" id="wx-cell-replay-guide">
                    <div class="wx-cell-icon green"><i class="fas fa-graduation-cap"></i></div>
                    <span class="wx-cell-label">重新查看新手引导</span>
                    <span class="wx-cell-value"></span>
                    <i class="fas fa-chevron-right wx-cell-arrow"></i>
                </div>
                <div class="wx-cell" id="wx-cell-about">
                    <div class="wx-cell-icon gray"><i class="fas fa-circle-info"></i></div>
                    <span class="wx-cell-label">关于粤乡智匠</span>
                    <span class="wx-cell-value">v1.0</span>
                    <i class="fas fa-chevron-right wx-cell-arrow"></i>
                </div>
            </div>
        </div>
    `);

    // 点击个人信息卡片 → 编辑资料子页面
    document.getElementById('wx-profile-card')?.addEventListener('click', () => {
        showSettingsSubPage('edit-profile', { name, email, username, roleLabel, createdAt });
    });

    // 通知公告（原「我的动态」，实为全局公告，见 showSettingsSubPage 注释）
    document.getElementById('wx-cell-my-posts')?.addEventListener('click', () => {
        showSettingsSubPage('my-posts', {});
    });

    // 深色模式开关
    document.getElementById('wx-dark-toggle')?.addEventListener('change', (e) => {
        const theme = e.target.checked ? 'dark' : 'light';
        document.documentElement.dataset.theme = theme;
        localStorage.setItem(STORAGE_KEYS.THEME, theme);
        updateThemeIcon();
    });

    // 新消息通知开关：是否接收教师 / 企业 / 超级管理员发布的系统公告
    document.getElementById('wx-notif-toggle')?.addEventListener('change', (e) => {
        setNotifEnabled(e.target.checked);
        showNotification(
            e.target.checked ? '已开启消息通知' : '已关闭消息通知，将不再接收系统公告',
            e.target.checked ? 'success' : 'info'
        );
        if (typeof updateBadgeCount === 'function') updateBadgeCount();
    });

    // 重新查看新手引导
    document.getElementById('wx-cell-replay-guide')?.addEventListener('click', () => {
        document.querySelector('.modal-overlay.detail-modal')?.remove();
        if (typeof showOnboarding === 'function') showOnboarding();
    });

    // 关于页面
    document.getElementById('wx-cell-about')?.addEventListener('click', () => {
        showSettingsSubPage('about', {});
    });
}

function showSettingsSubPage(page, data) {
    const modalBody = document.querySelector('.modal-overlay.detail-modal .modal-body');
    if (!modalBody) return;

    if (page === 'edit-profile') {
        modalBody.innerHTML = `
            <div class="wx-sub-page">
                <div class="wx-sub-header">
                    <button class="wx-back-btn" onclick="showSettingsModal()"><i class="fas fa-chevron-left"></i> 返回</button>
                    <span class="wx-sub-title">个人信息</span>
                    <button class="wx-save-btn" id="wx-save-profile">保存</button>
                </div>
                <div class="wx-cell-group">
                    <div class="wx-cell">
                        <span class="wx-cell-label">姓名</span>
                        <input type="text" class="wx-cell-input" id="wx-edit-name" value="${data.name}" placeholder="请输入姓名">
                    </div>
                    <div class="wx-cell">
                        <span class="wx-cell-label">邮箱</span>
                        <input type="text" class="wx-cell-input" id="wx-edit-email" value="${data.email}" placeholder="请输入邮箱">
                    </div>
                </div>
                <div class="wx-cell-group">
                    <div class="wx-cell">
                        <span class="wx-cell-label">用户名</span>
                        <span class="wx-cell-value">${data.username}</span>
                    </div>
                    <div class="wx-cell">
                        <span class="wx-cell-label">身份</span>
                        <span class="wx-cell-value">${data.roleLabel}</span>
                    </div>
                    ${data.createdAt ? `<div class="wx-cell">
                        <span class="wx-cell-label">注册时间</span>
                        <span class="wx-cell-value">${data.createdAt}</span>
                    </div>` : ''}
                </div>
                <div class="wx-cell-group">
                    <div class="wx-cell clickable" id="wx-change-password">
                        <span class="wx-cell-label">修改密码</span>
                        <span class="wx-cell-value"></span>
                        <i class="fas fa-chevron-right wx-cell-arrow"></i>
                    </div>
                </div>
            </div>
        `;

        // 保存资料
        document.getElementById('wx-save-profile')?.addEventListener('click', async () => {
            const name = document.getElementById('wx-edit-name')?.value.trim();
            const email = document.getElementById('wx-edit-email')?.value.trim();
            if (!name) { showNotification('姓名不能为空', 'error'); return; }
            try {
                const res = await apiCall('/api/user/profile', 'PUT', { name, email });
                showNotification(res.message, res.success ? 'success' : 'error');
                if (res.success) {
                    if (AppState.user) { AppState.user.name = name; AppState.user.email = email; }
                    updateUserUI();
                }
            } catch(e) { showNotification('保存失败', 'error'); }
        });

        // 修改密码子页面
        document.getElementById('wx-change-password')?.addEventListener('click', () => {
            showSettingsSubPage('change-password', {});
        });

    } else if (page === 'change-password') {
        modalBody.innerHTML = `
            <div class="wx-sub-page">
                <div class="wx-sub-header">
                    <button class="wx-back-btn" onclick="showSettingsSubPage('edit-profile', {name:'${data.name||''}',email:'${data.email||''}',username:'${data.username||''}',roleLabel:'${data.roleLabel||''}',createdAt:'${data.createdAt||''}'}"><i class="fas fa-chevron-left"></i> 返回</button>
                    <span class="wx-sub-title">修改密码</span>
                    <span></span>
                </div>
                <div class="wx-cell-group">
                    <div class="wx-cell">
                        <span class="wx-cell-label">当前密码</span>
                        <input type="password" class="wx-cell-input" id="wx-old-pwd" placeholder="请输入当前密码">
                    </div>
                    <div class="wx-cell">
                        <span class="wx-cell-label">新密码</span>
                        <input type="password" class="wx-cell-input" id="wx-new-pwd" placeholder="至少6位">
                    </div>
                    <div class="wx-cell">
                        <span class="wx-cell-label">确认密码</span>
                        <input type="password" class="wx-cell-input" id="wx-confirm-pwd" placeholder="再次输入新密码">
                    </div>
                </div>
                <div class="wx-btn-wrap">
                    <button class="wx-primary-btn" id="wx-save-password">完成</button>
                </div>
            </div>
        `;
        document.getElementById('wx-save-password')?.addEventListener('click', async () => {
            const old_password = document.getElementById('wx-old-pwd')?.value;
            const new_password = document.getElementById('wx-new-pwd')?.value;
            const confirm_password = document.getElementById('wx-confirm-pwd')?.value;
            if (!old_password || !new_password || !confirm_password) {
                showNotification('请填写完整', 'error'); return;
            }
            try {
                const res = await apiCall('/api/user/password', 'PUT', { old_password, new_password, confirm_password });
                showNotification(res.message, res.success ? 'success' : 'error');
                if (res.success) showSettingsModal();
            } catch(e) { showNotification('修改失败', 'error'); }
        });

    } else if (page === 'about') {
        modalBody.innerHTML = `
            <div class="wx-sub-page">
                <div class="wx-sub-header">
                    <button class="wx-back-btn" onclick="showSettingsModal()"><i class="fas fa-chevron-left"></i> 返回</button>
                    <span class="wx-sub-title">关于粤乡智匠</span>
                    <span></span>
                </div>
                <div class="wx-about">
                    <div class="wx-about-logo">
                        <i class="fas fa-seedling"></i>
                    </div>
                    <h3 class="wx-about-name">粤乡智匠</h3>
                    <p class="wx-about-version">版本 1.0.0</p>
                    <p class="wx-about-desc">AI驱动的农村人才赋能平台</p>
                </div>
                <div class="wx-cell-group">
                    <div class="wx-cell">
                        <span class="wx-cell-label">功能模块</span>
                        <span class="wx-cell-value">农产品文案 · 农技指导 · 非遗传承</span>
                    </div>
                    <div class="wx-cell">
                        <span class="wx-cell-label">教学管理</span>
                        <span class="wx-cell-value">通知 · 作业 · 批改 · 分析</span>
                    </div>
                    <div class="wx-cell">
                        <span class="wx-cell-label">技术支持</span>
                        <span class="wx-cell-value">AI + Flask + SQLite</span>
                    </div>
                </div>
            </div>
        `;

    } else if (page === 'my-posts') {
        // P1-6：这里展示的是平台/教师的**全局通知公告**（后端按 limit 取，不按用户过滤），
        // 原叫「我的动态」属名实不符，改为如实命名。
        modalBody.innerHTML = `
            <div class="wx-sub-page">
                <div class="wx-sub-header">
                    <button class="wx-back-btn" onclick="showSettingsModal()"><i class="fas fa-chevron-left"></i> 返回</button>
                    <span class="wx-sub-title">通知公告</span>
                    <span></span>
                </div>
                <div id="wx-posts-list" class="wx-list-container">
                    <div class="wx-loading"><div class="spinner"></div> 加载中...</div>
                </div>
            </div>
        `;
        loadMyPosts();

    }
}

async function loadMyPosts() {
    const container = document.getElementById('wx-posts-list');
    if (!container) return;
    try {
        const data = await apiCall('/api/student/announcements');
        if (!data.success || !data.announcements.length) {
            container.innerHTML = '<div class="wx-empty"><i class="fas fa-bullhorn"></i><p>暂无公告</p></div>';
            return;
        }
        container.innerHTML = `<div class="wx-cell-group">${data.announcements.map(a => {
            const catColors = { '通知': 'blue', '公告': 'gray', '紧急': 'orange' };
            const catCls = catColors[a.category] || 'blue';
            // 公告由教师/管理员撰写，字段一律转义后再拼进 HTML，避免注入
            return `
                <div class="wx-cell vertical">
                    <div class="wx-cell-top">
                        <span class="wx-tag ${catCls}">${escapeHtml(a.category || '')}</span>
                        ${a.pinned ? '<span class="wx-tag pin">置顶</span>' : ''}
                        <span class="wx-cell-time">${escapeHtml(a.created_at || '')}</span>
                    </div>
                    <span class="wx-cell-title">${escapeHtml(a.title || '')}</span>
                    <span class="wx-cell-desc">${escapeHtml(a.content || '')}</span>
                </div>
            `;
        }).join('')}</div>`;
    } catch(e) {
        container.innerHTML = '<div class="wx-empty">公告加载失败，请稍后重试</div>';
    }
}

// ==================== 农产品选择 ====================

function setupProductSelection() {
    // 恢复上次选择的作物（localStorage）；HTML 中不再硬编码 active，统一由这里同步
    const cards = document.querySelectorAll('.product-card');
    const saved = (() => {
        try { return localStorage.getItem('yuexiang_farming_product'); } catch (e) { return null; }
    })();
    const target = (saved && document.querySelector(`.product-card[data-product="${saved}"]`))
        || document.querySelector('.product-card');
    if (target && cards.length) {
        cards.forEach(c => c.classList.remove('active'));
        target.classList.add('active');
        AppState.currentProduct = target.dataset.product;
    }

    setupSelectionHandler('.product-card', 'active', 'currentProduct', (card) => {
        const pid = card.dataset.product;
        if (pid) {
            AppState.currentProduct = pid;
            try { localStorage.setItem('yuexiang_farming_product', pid); } catch (e) { /* 忽略隐私模式异常 */ }
        }
        updateFarmingCalendar();
        syncFarmingSubscriptionButton();
        // A1：顶部作物变了，诊断面板的作物必须跟着换 —— 否则学生照着水稻症状提交，
        // 拿到一份写在柑橘名下的结论，界面上还不会提示。这里显式复位「用户手选过」的门禁
        // 再同步一次；面板内手选仍然不会被「收起再展开」静默改掉（见 syncPestCropFromProduct）。
        resetPestCropToCurrent();
        // A4：速查的作物筛选同理跟随 —— 同一个页面里「当前作物」只应有一套含义。
        resetPestGuideCropToCurrent();
    });
}

// ==================== 手工艺选择 ====================

function setupCraftSelection() {
    setupSelectionHandler('.craft-card', 'active', 'currentCraft', () => {
        updateCraftSteps();
        loadCraftModels();
    });
}

async function updateCraftSteps() {
    const container = document.getElementById('craft-steps');
    if (!container) return;
    showSkeleton(container, 'text', 4);
    // P1-9：材料采购指南必须随手工艺同步刷新。先置加载态，
    // 否则切到手工艺的请求还没回来时，页面会残留上一个手工艺（广绣）的采购卡。
    const materialsSection = document.getElementById('materials-section');
    if (materialsSection) showSkeleton(materialsSection, 'card', 3);

    try {
        const data = await apiCall(`/api/crafts/${AppState.currentCraft}`);
        if (data.success && data.data) {
            // 渲染文化背景卡（② 2026-10-06：展示 history/origin/name，让非遗不只技法）
            renderCraftIntro(data.data);

            // 渲染步骤
            if (data.data.steps && data.data.steps.length > 0) {
                container.innerHTML = data.data.steps.map((s, i) => `
                    <div class="step${i === 0 ? ' active' : ''}" data-step-index="${i}">
                        <span class="step-number">${i + 1}</span>
                        <div class="step-content">
                            <h5>${s.title}</h5>
                            <p>${s.desc}</p>
                            ${s.tips ? `<div class="step-tips"><i class="fas fa-lightbulb"></i> ${s.tips}</div>` : ''}
                        </div>
                    </div>
                `).join('');
                // 步骤点击 → 3D 视角联动（2026-10-06）
                container.querySelectorAll('.step').forEach(stepEl => {
                    stepEl.addEventListener('click', () => {
                        const idx = parseInt(stepEl.dataset.stepIndex, 10);
                        container.querySelectorAll('.step').forEach(e => e.classList.remove('active'));
                        stepEl.classList.add('active');
                        focusCraftStep(idx, data.data.steps.length);
                        // ③ 学习进度：点击步骤即标记为已完成（含之前的所有步骤）
                        markCraftStepsComplete(idx);
                    });
                });
                // ③ 恢复学习进度高亮（切手工艺后重渲染步骤时回填）
                applyCraftProgress(data.data.steps.length);
            } else {
                showEmptyState(container, 'fa-paint-brush', '暂无步骤', '该手工艺的步骤正在准备中');
            }

            // 渲染材料采购指南（详细采购手册）
            const guide = data.data.purchase_guide;
            if (guide && guide.categories) {
                renderPurchaseGuide(guide);
            } else if (materialsSection) {
                // 该手工艺没有采购清单：如实出空态，绝不沿用上一个手工艺的数据
                showEmptyState(materialsSection, 'fa-shopping-basket', '暂无材料采购指南', '该手工艺的采购清单正在整理中');
            }
        }
    } catch(e) {
        showErrorState(container, '加载手工艺步骤失败', () => updateCraftSteps());
        // 材料指南同样回到错误态并提供重试，不留旧数据
        if (materialsSection) {
            showErrorState(materialsSection, '材料采购指南加载失败', () => updateCraftSteps());
        }
    }
}

// ② 文化背景卡：展示手工艺的产地与历史渊源
function renderCraftIntro(craft) {
    const el = document.getElementById('craft-intro');
    if (!el) return;
    const name = craft.name || '';
    const origin = craft.origin || '';
    const history = craft.history || '';
    if (!history && !origin) {
        el.innerHTML = '';
        el.style.display = 'none';
        return;
    }
    el.style.display = '';
    el.innerHTML = `
        <div class="craft-intro-card">
            <div class="craft-intro-icon"><i class="fas fa-landmark"></i></div>
            <div class="craft-intro-body">
                <div class="craft-intro-head">
                    <h3>${escapeHtml(name)}</h3>
                    ${origin ? `<span class="craft-intro-origin"><i class="fas fa-map-marker-alt"></i> ${escapeHtml(origin)}</span>` : ''}
                </div>
                ${history ? `<p>${escapeHtml(history)}</p>` : ''}
            </div>
        </div>
    `;
}

// ③ 学习进度：每个手工艺独立记录「已完成的步骤数」（持久化到 localStorage）。
// 点击某一步即认为「学到了这一步」，之前的步骤也都算完成。
function getCraftProgressKey(craft) {
    return 'yuexiang_craft_progress_' + (craft || 'embroidery');
}

function markCraftStepsComplete(stepIndex) {
    const craft = AppState.currentCraft || 'embroidery';
    const key = getCraftProgressKey(craft);
    let done = 0;
    try { done = parseInt(localStorage.getItem(key), 10) || 0; } catch (e) {}
    // 完成数 = max(已记录, 当前步+1)
    const next = Math.max(done, stepIndex + 1);
    try { localStorage.setItem(key, String(next)); } catch (e) {}
    applyCraftProgress();
}

// 回填：切手工艺后重渲染步骤时，把已完成步骤标记出来 + 更新进度条
function applyCraftProgress(totalSteps) {
    const craft = AppState.currentCraft || 'embroidery';
    const key = getCraftProgressKey(craft);
    let done = 0;
    try { done = parseInt(localStorage.getItem(key), 10) || 0; } catch (e) {}
    // 上限取「传入的步骤总数」或「当前 DOM 里的步骤数」（无参调用时用后者兜底）
    const total = totalSteps || document.querySelectorAll('#craft-steps .step').length || 0;
    done = Math.max(0, Math.min(done, total));

    // 给已完成步骤加 .is-done 标记
    const steps = document.querySelectorAll('#craft-steps .step');
    steps.forEach((el, i) => {
        el.classList.toggle('is-done', i < done);
    });

    // 更新进度条
    const pct = total > 0 ? Math.round((done / total) * 100) : 0;
    const fill = document.getElementById('craft-progress-fill');
    const text = document.getElementById('craft-progress-text');
    if (fill) fill.style.width = pct + '%';
    if (text) text.textContent = `已完成 ${done}/${total} 步`;
}

const CATEGORY_META = {
    essential: { icon: 'fa-circle-check', cls: 'essential', badge: '必买' },
    consumable: { icon: 'fa-boxes-stacked', cls: 'consumable', badge: '常备' },
    advanced: { icon: 'fa-sliders', cls: 'advanced', badge: '选配' }
};

// 从价格字符串（如"35-80元"、"20-40元/10斤"）解析数值区间，汇总分组小计
function calcCategorySubtotal(items) {
    let minSum = 0, maxSum = 0, hasPrice = false;
    items.forEach(m => {
        if (!m.price) return;
        const head = String(m.price).split('元')[0];
        const nums = (head.match(/\d+(?:\.\d+)?/g) || []).map(Number);
        if (nums.length === 0) return;
        hasPrice = true;
        minSum += Math.min(...nums);
        maxSum += Math.max(...nums);
    });
    return hasPrice ? `小计约 ${minSum}-${maxSum} 元` : '';
}

function renderPurchaseGuide(guide) {
    const section = document.getElementById('materials-section');
    if (!section) return;

    const catHtml = guide.categories.map((cat, idx) => {
        const meta = CATEGORY_META[cat.key] || CATEGORY_META.essential;
        const open = idx === 0; // 必买组默认展开，其余收起
        const subtotal = calcCategorySubtotal(cat.items);
        const items = cat.items.map(m => `
            <div class="guide-item ${meta.cls}">
                <div class="guide-item-head">
                    <span class="guide-badge ${meta.cls}">${meta.badge}</span>
                    <h5>${m.name}</h5>
                    <span class="price-tag">${m.price}</span>
                </div>
                ${m.spec ? `<div class="guide-spec"><i class="fas fa-ruler-combined"></i> <b>怎么选：</b>${m.spec}</div>` : ''}
                ${m.where ? `<div class="guide-where"><i class="fas fa-map-marker-alt"></i> <b>去哪买：</b>${m.where}</div>` : ''}
                ${m.tip ? `<div class="guide-tip"><i class="fas fa-lightbulb"></i> <b>避坑提示：</b>${m.tip}</div>` : ''}
            </div>
        `).join('');
        return `
            <div class="guide-category ${meta.cls}${open ? ' open' : ''}">
                <button type="button" class="guide-cat-head" aria-expanded="${open}">
                    <i class="fas ${meta.icon}"></i>
                    <span>${cat.label}</span>
                    <small>${cat.desc || ''}</small>
                    <span class="guide-cat-meta">
                        ${subtotal ? `<b class="guide-subtotal">${subtotal}</b>` : ''}
                        <em class="guide-count">${cat.items.length} 项</em>
                        <i class="fas fa-chevron-down guide-chevron"></i>
                    </span>
                </button>
                <div class="guide-body">
                    <div class="guide-items">${items}</div>
                </div>
            </div>
        `;
    }).join('');

    section.innerHTML = `
        <h3 class="card-section-title"><i class="fas fa-shopping-basket"></i> 材料采购指南</h3>
        ${guide.budget ? `
        <div class="guide-budget">
            <div class="budget-item starter">
                <i class="fas fa-piggy-bank"></i>
                <div><small>入门全套预算</small><b>${guide.budget.starter}</b></div>
            </div>
            <div class="budget-item advanced">
                <i class="fas fa-chart-line"></i>
                <div><small>进阶全套预算</small><b>${guide.budget.advanced}</b></div>
            </div>
        </div>` : ''}
        ${guide.buying_tips ? `
        <div class="guide-buying-tips">
            <i class="fas fa-compass"></i>
            <div><b>学员采购建议：</b>${guide.buying_tips}</div>
        </div>` : ''}
        <div class="guide-toolbar">
            <button type="button" class="btn btn-text btn-sm" id="guide-toggle-all">全部展开 <i class="fas fa-angles-down"></i></button>
        </div>
        ${catHtml}
    `;

    // 折叠交互：点击分组标题栏切换展开/收起
    const catEls = section.querySelectorAll('.guide-category');
    catEls.forEach(catEl => {
        catEl.querySelector('.guide-cat-head').addEventListener('click', () => {
            const open = catEl.classList.toggle('open');
            catEl.querySelector('.guide-cat-head').setAttribute('aria-expanded', open);
            syncToggleAllText();
        });
    });

    // 全部展开 / 全部收起
    const toggleAllBtn = document.getElementById('guide-toggle-all');
    function syncToggleAllText() {
        if (!toggleAllBtn) return;
        const allOpen = [...catEls].every(c => c.classList.contains('open'));
        toggleAllBtn.innerHTML = allOpen
            ? '全部收起 <i class="fas fa-angles-up"></i>'
            : '全部展开 <i class="fas fa-angles-down"></i>';
    }
    toggleAllBtn?.addEventListener('click', () => {
        const allOpen = [...catEls].every(c => c.classList.contains('open'));
        catEls.forEach(c => {
            c.classList.toggle('open', !allOpen);
            c.querySelector('.guide-cat-head').setAttribute('aria-expanded', !allOpen);
        });
        syncToggleAllText();
    });
}

// ==================== 方言选择 ====================

const VoiceState = {
    history: [],
    maxHistory: 10,
    isRecording: false,
    recognition: null,
    // TTS 朗读状态机：idle（未读）/ speaking（朗读中）/ paused（已暂停）
    ttsState: 'idle',
    ttsBtn: null,       // 当前朗读按钮引用
    ttsUtter: null,     // 当前 utterance 引用（用于忽略过期回调）
    ttsTimer: null,     // Chrome 长文本 keep-alive 定时器
    inputHintTimer: null // 语音输入框错误提示的自动恢复定时器
};

// 语音输入框默认占位文案（错误提示用完必须恢复，别让一次错误常驻）
const VOICE_INPUT_DEFAULT_PLACEHOLDER = '输入你的问题...';

// 方言 → 语音识别语言映射（SpeechRecognition.lang）
// 粤语用 zh-HK（广东话）；客家话/潮汕话主流浏览器无对应语言包，
// 用 zh-CN 兜底（识别普通话转写，仍可送后端用方言回答）。
const DIALECT_SPEECH_LANG = {
    cantonese: 'zh-HK',
    hakka: 'zh-CN',
    teochew: 'zh-CN'
};

// 方言 → 语音合成（TTS）语言映射，speechSynthesis.lang
const DIALECT_TTS_LANG = {
    cantonese: 'zh-HK',
    hakka: 'zh-CN',
    teochew: 'zh-CN'
};

function setupDialectSelection() {
    // 方言卡片点击
    document.querySelectorAll('.dialect-card').forEach(card => {
        card.addEventListener('click', function() {
            document.querySelectorAll('.dialect-card').forEach(c => c.classList.remove('active'));
            this.classList.add('active');
            AppState.currentDialect = this.dataset.dialect;
            loadDialectInfo(AppState.currentDialect);
        });
    });
    // P1-8：卡片上的「覆盖区域 / 使用者数」此前是 HTML 硬编码，且与后端 DIALECTS_DATA
    // （areas/speakers）不一致 → 改为以后端为准回填，避免两处文案各说各话。
    loadDialectCards();
}

async function loadDialectCards() {
    const cards = document.querySelectorAll('.dialect-card');
    if (!cards.length) return;
    try {
        const data = await apiCall('/api/resources/dialects');
        if (!data.success || !Array.isArray(data.dialects)) return;
        const byId = {};
        data.dialects.forEach(d => { if (d && d.id) byId[d.id] = d; });
        cards.forEach(card => {
            const d = byId[card.dataset.dialect];
            if (!d) return;   // 后端没有这个方言：保持预置值，不臆造
            const strong = card.querySelector('.dialect-card-header strong');
            if (strong && d.name) strong.textContent = d.name;
            const regionEl = card.querySelector('.dialect-card-header div > span');
            if (regionEl && d.region) regionEl.textContent = d.region;
            const metaSpans = card.querySelectorAll('.dialect-card-meta > span');
            if (metaSpans[0] && d.areas) {
                metaSpans[0].innerHTML = '<i class="fas fa-map-marker-alt"></i> ' + escapeHtml(d.areas);
            }
            if (metaSpans[1] && d.speakers) {
                metaSpans[1].innerHTML = '<i class="fas fa-users"></i> ' + escapeHtml(d.speakers);
            }
        });
    } catch (e) {
        // 取不到时保留 HTML 预置值（与后端同源），不静默清空成空白卡片
    }
}

// ==================== 语音输入 ====================

function setupVoiceInput() {
    const voiceBtn = document.getElementById('voice-record-btn');
    const sendBtn = document.getElementById('voice-send-btn');
    const textInput = document.getElementById('voice-text-input');
    const clearBtn = document.getElementById('clear-voice-chat');

    if (!voiceBtn) return;

    // 语音按钮
    voiceBtn.addEventListener('click', function() {
        if (VoiceState.isRecording) {
            stopRecording();
            return;
        }
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (SpeechRecognition) {
            startSpeechRecognition();
        } else {
            // ⚠️ 此处原有一段「假演示」：不支持语音识别时，点麦克风会在 2 秒后
            //    自动发送固定问题「请问荔枝什么时候施肥最好？」，并在聊天区
            //    显示成学员自己的提问。学员从未说过这句话 —— 属于伪造用户输入，
            //    与项目「不冒充、失败必须可见」的红线直接冲突，已移除。
            //    改为如实告知不支持，并指向可用的文字输入。
            setVoiceInputHint('当前浏览器不支持语音识别，请用下方文字输入');
            showNotification('当前浏览器不支持语音识别，请改用文字输入提问', 'warning');
        }
    });

    // 发送按钮
    sendBtn?.addEventListener('click', () => {
        const text = textInput?.value?.trim();
        if (text) {
            sendVoiceMessage(text);
            textInput.value = '';
        }
    });

    // 回车发送
    textInput?.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            const text = textInput.value.trim();
            if (text) {
                sendVoiceMessage(text);
                textInput.value = '';
            }
        }
    });

    // 清空对话
    clearBtn?.addEventListener('click', () => {
        stopSpeak();
        VoiceState.history = [];
        const messages = document.getElementById('voice-chat-messages');
        if (messages) {
            messages.innerHTML = `<div class="voice-welcome"><i class="fas fa-robot"></i><p>你好！我是方言农业助手，可以用普通话或方言向我提问</p></div>`;
        }
    });

    // 加载默认方言信息
    loadDialectInfo(AppState.currentDialect || 'cantonese');
}

// 语音输入框提示：临时显示错误文案，并在「重新录音 / 识别成功 / 超时」后恢复默认。
// 修 bug：此前把错误写进 placeholder 后从不恢复，一次「未检测到麦克风」会永久占位。
function setVoiceInputHint(msg) {
    const el = document.getElementById('voice-text-input');
    if (el) el.placeholder = msg;
    if (VoiceState.inputHintTimer) clearTimeout(VoiceState.inputHintTimer);
    VoiceState.inputHintTimer = setTimeout(clearVoiceInputHint, 6000);
}
function clearVoiceInputHint() {
    const el = document.getElementById('voice-text-input');
    if (el) el.placeholder = VOICE_INPUT_DEFAULT_PLACEHOLDER;
    if (VoiceState.inputHintTimer) {
        clearTimeout(VoiceState.inputHintTimer);
        VoiceState.inputHintTimer = null;
    }
}

function startSpeechRecognition() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    const recognition = new SpeechRecognition();
    recognition.lang = DIALECT_SPEECH_LANG[AppState.currentDialect] || 'zh-CN';
    recognition.interimResults = true;
    recognition.continuous = false;
    VoiceState.recognition = recognition;
    VoiceState.isRecording = true;

    // 重新开始录音 → 清掉上一次残留的错误提示
    clearVoiceInputHint();

    const voiceBtn = document.getElementById('voice-record-btn');
    voiceBtn?.classList.add('recording');

    recognition.onresult = function(event) {
        const transcript = event.results[0][0].transcript;
        const textInput = document.getElementById('voice-text-input');
        if (textInput) textInput.value = transcript;
        // 有识别结果 = 麦克风正常，清掉错误提示
        clearVoiceInputHint();
        if (event.results[0].isFinal) {
            sendVoiceMessage(transcript);
            if (textInput) textInput.value = '';
        }
    };

    recognition.onerror = function(event) {
        // 按错误类型给明确提示，不再静默失败
        const map = {
            'not-allowed': '麦克风权限被拒绝，请在浏览器地址栏允许麦克风后重试',
            'service-not-allowed': '麦克风权限被拒绝，请在浏览器地址栏允许麦克风后重试',
            'audio-capture': '未检测到麦克风设备，请确认麦克风已连接',
            'no-speech': '没有听到声音，请靠近麦克风再试一次',
            'network': '语音识别网络异常，请检查网络后重试',
            'aborted': '已停止录音'
        };
        const msg = map[event.error] || ('语音识别失败：' + event.error);
        if (event.error !== 'aborted' && event.error !== 'no-speech') {
            setVoiceInputHint(msg);
        }
        // 用通知条提示（复用项目通知组件）
        if (event.error !== 'aborted') {
            showNotification(msg, event.error === 'not-allowed' || event.error === 'service-not-allowed' ? 'warning' : 'error');
        }
        stopRecording();
    };

    recognition.onend = function() {
        stopRecording();
    };

    recognition.start();
}

function stopRecording() {
    VoiceState.isRecording = false;
    const voiceBtn = document.getElementById('voice-record-btn');
    voiceBtn?.classList.remove('recording');
    if (VoiceState.recognition) {
        try { VoiceState.recognition.stop(); } catch(e) {}
    }
}

// 属性值转义：escapeHtml 走 textContent→innerHTML，不转引号，拼进属性前必须补一道
function attrEsc(s) {
    return escapeHtml(String(s == null ? '' : s)).replace(/"/g, '&quot;');
}

async function loadDialectInfo(dialectId) {
    try {
        const data = await apiCall(`/api/resources/dialect-info?dialect=${dialectId}`);
        // ⚠️ 必须校验返回的 id 与请求的一致：后端对未知方言是
        //    `DIALECTS_DATA.get(id, DIALECTS_DATA['cantonese'])` —— **静默回退成粤语**。
        //    不校验的话，学员点「潮汕话」，卡片高亮潮汕话、下面显示的却是粤语内容。
        if (!data.success || !data.info || data.info.id !== dialectId) {
            throw new Error('方言资料返回异常');
        }
        renderDialectInfo(data.info);
    } catch(e) {
        // 不能静默失败（原实现 catch 里只有一句注释）：
        // 否则卡片已经高亮成新方言，内容还停在上一个方言，界面自相矛盾 ——
        // 学员会以为「潮汕话和粤语一模一样」，或者以为点错了没反应。
        renderDialectError(dialectId);
    }
}

// 方言资料取不到时：清掉上一个方言的内容并如实说明，不留旧方言残影
function renderDialectError(dialectId) {
    const card = document.querySelector(`.dialect-card[data-dialect="${dialectId}"] strong`);
    const name = card ? card.textContent : '该方言';
    const greetingMain = document.getElementById('greeting-main');
    const greetingMeaning = document.getElementById('greeting-meaning');
    if (greetingMain) greetingMain.textContent = '资料加载失败';
    if (greetingMeaning) greetingMeaning.textContent = `（${name}的问候语与常用短语暂时取不到，请重新点击该方言重试）`;
    // 特征标签 / 短语 / 快捷问题都清空 —— 宁可空着，也不能拿上一个方言的内容冒充
    const featuresEl = document.getElementById('dialect-features');
    if (featuresEl) featuresEl.innerHTML = '';
    const phrasesGrid = document.getElementById('phrases-grid');
    if (phrasesGrid) phrasesGrid.innerHTML = '';
    const quickEl = document.getElementById('voice-quick-questions');
    if (quickEl) quickEl.innerHTML = '';
    // 短语区整块收起：否则会留下一个「常用短语」标题配一片空白，看起来像加载到一半
    togglePhrasesPanel(false);
}

// 常用短语区：没有短语时整块收起（失败态、或该方言确实没有短语）
function togglePhrasesPanel(show) {
    const panel = document.querySelector('.phrases-panel');
    if (panel) panel.style.display = show ? '' : 'none';
}

function renderDialectInfo(info) {
    // 问候语
    const greetingMain = document.getElementById('greeting-main');
    const greetingMeaning = document.getElementById('greeting-meaning');
    if (greetingMain) greetingMain.textContent = info.greeting || '';
    if (greetingMeaning) greetingMeaning.textContent = `（${info.greeting_meaning || ''}）`;

    // 特征标签（无条件重写：字段缺失时清空，避免残留上一个方言的标签）
    const featuresEl = document.getElementById('dialect-features');
    if (featuresEl) {
        featuresEl.innerHTML = (info.features || [])
            .map(f => `<span class="feature-tag">${escapeHtml(f)}</span>`).join('');
    }

    // 常用短语（同样无条件重写）
    const phrasesGrid = document.getElementById('phrases-grid');
    if (phrasesGrid) {
        phrasesGrid.innerHTML = (info.phrases || []).map(p =>
            `<div class="phrase-item" data-text="${attrEsc(p.dialect)}" title="点击发送：${attrEsc(p.dialect)}">
                <span class="phrase-dialect">${escapeHtml(p.dialect)}</span>
                <span class="phrase-mandarin">${escapeHtml(p.mandarin)}</span>
                <span class="phrase-pinyin">${escapeHtml(p.pinyin || '')}</span>
            </div>`
        ).join('');
        togglePhrasesPanel((info.phrases || []).length > 0);
        // 点击短语发送
        phrasesGrid.querySelectorAll('.phrase-item').forEach(item => {
            item.addEventListener('click', () => {
                sendVoiceMessage(item.dataset.text);
            });
        });
    }

    // 快捷问题（同样无条件重写）
    const quickEl = document.getElementById('voice-quick-questions');
    if (quickEl) {
        quickEl.innerHTML = (info.quick_questions || []).map(q =>
            `<button class="voice-quick-btn">${escapeHtml(q)}</button>`
        ).join('');
        quickEl.querySelectorAll('.voice-quick-btn').forEach(btn => {
            btn.addEventListener('click', () => sendVoiceMessage(btn.textContent));
        });
    }
}

async function sendVoiceMessage(text) {
    const messagesEl = document.getElementById('voice-chat-messages');
    if (!messagesEl) return;

    // 发新消息前先停掉正在朗读/暂停的内容，避免新旧语音叠着念
    stopSpeak();

    // 移除欢迎消息
    const welcome = messagesEl.querySelector('.voice-welcome');
    if (welcome) welcome.remove();

    // 显示用户消息
    const userMsg = document.createElement('div');
    userMsg.className = 'voice-msg user';
    userMsg.textContent = text;
    messagesEl.appendChild(userMsg);
    messagesEl.scrollTop = messagesEl.scrollHeight;

    // 显示加载状态
    const loadingMsg = document.createElement('div');
    loadingMsg.className = 'voice-msg bot';
    loadingMsg.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 思考中...';
    messagesEl.appendChild(loadingMsg);
    messagesEl.scrollTop = messagesEl.scrollHeight;

    try {
        const data = await apiCall('/api/resources/voice', 'POST', {
            text: text,
            dialect: AppState.currentDialect || 'cantonese',
            history: VoiceState.history
        });

        loadingMsg.remove();

        if (data.success && data.result) {
            const r = data.result;
            const botMsg = document.createElement('div');
            botMsg.className = 'voice-msg bot';
            let html = '';
            if (r.dialect_name) {
                html += `<div class="msg-dialect-tag">${r.dialect_name}助手</div>`;
            }
            html += `<div class="voice-msg-body">${formatAnswer(r.answer || '暂无回答')}</div>`;
            // 朗读 + 诚实标注（P2/P3）
            const hasTTS = 'speechSynthesis' in window;
            html += `<div class="voice-msg-actions">`;
            if (hasTTS) {
                html += `<button class="voice-speak-btn" data-answer="${encodeURIComponent(r.answer || '')}" title="朗读回答"><i class="fas fa-volume-up"></i> 朗读</button>`;
                html += `<button class="voice-stop-btn" style="display:none" title="停止朗读"><i class="fas fa-stop"></i> 停止</button>`;
            }
            // 诚实标注：AI 方言回答不一定地道，降级话术库同样标注来源
            const note = r.source === 'fallback'
                ? '（本地方言语料库回答，仅供学习参考）'
                : '（AI 方言回答，仅供学习参考，个别用词可能与当地口语有差异）';
            html += `<span class="voice-msg-note">${note}</span>`;
            html += `</div>`;
            // 用药提示：回答里出现用量 / 稀释倍数 / 安全间隔期时，由服务端单独下发。
            // 与农技问答、病虫害诊断同一条红线 —— 给了用量就必须给用户提示，
            // 不能因为「这是方言版」就少一句免责声明。
            if (r.chem_notice) {
                html += `<div class="voice-msg-chem"><i class="fas fa-exclamation-triangle"></i>${escapeHtml(r.chem_notice)}</div>`;
            }
            if (r.suggestions && r.suggestions.length) {
                html += `<div class="msg-suggestions">${r.suggestions.map(s =>
                    `<span class="suggestion-btn">${s}</span>`
                ).join('')}</div>`;
            }
            botMsg.innerHTML = html;
            messagesEl.appendChild(botMsg);

            // 朗读按钮（三态：朗读 → 暂停 → 继续）
            botMsg.querySelectorAll('.voice-speak-btn').forEach(btn => {
                btn.addEventListener('click', () => speakAnswer(decodeURIComponent(btn.dataset.answer), btn));
            });
            // 停止按钮
            botMsg.querySelectorAll('.voice-stop-btn').forEach(btn => {
                btn.addEventListener('click', () => stopSpeak());
            });

            // 追问按钮点击
            botMsg.querySelectorAll('.suggestion-btn').forEach(btn => {
                btn.addEventListener('click', () => sendVoiceMessage(btn.textContent));
            });

            // 保存历史
            VoiceState.history.push({ user: text, bot: r.answer });
            if (VoiceState.history.length > VoiceState.maxHistory) {
                VoiceState.history = VoiceState.history.slice(-VoiceState.maxHistory);
            }
        } else {
            // success 但没有 result —— 也必须让学员看见失败。
            // loading 气泡此时已被移除，若什么都不做，界面会停在学员提问后一动不动，
            // 看起来像「问完就没反应了」（违反「失败必须可见」）。
            const emptyMsg = document.createElement('div');
            emptyMsg.className = 'voice-msg bot';
            emptyMsg.textContent = '抱歉，这次没有拿到回答，请再问一次';
            messagesEl.appendChild(emptyMsg);
        }
    } catch(e) {
        loadingMsg.remove();
        const errMsg = document.createElement('div');
        errMsg.className = 'voice-msg bot';
        // 按服务端下发的 code 给出针对性提示（apiCall 失败时带 err.status / err.code）
        if (e && e.status === 429) {
            errMsg.textContent = '提问过于频繁，请稍后再试';
        } else if (e && e.code === 'ai_not_configured') {
            errMsg.textContent = '该功能尚未启用，请联系管理员';
        } else {
            errMsg.textContent = '抱歉，暂时无法回答，请稍后再试';
        }
        messagesEl.appendChild(errMsg);
    }

    messagesEl.scrollTop = messagesEl.scrollHeight;
}

// ==================== 语音合成（TTS 朗读） ====================
// 三态：朗读 → 暂停 → 继续；另有独立的「停止」。
// ⚠️ 暂停必须用 speechSynthesis.pause()（保留播放位置），不能用 cancel()
//    —— cancel() 会丢弃进度，之后再 speak() 就是从头读（用户报过这个 bug）。

function speakAnswer(text, btn) {
    if (!('speechSynthesis' in window)) {
        showNotification('当前浏览器不支持语音朗读', 'warning');
        return;
    }
    // 同一按钮：朗读中 → 暂停；暂停中 → 继续
    if (VoiceState.ttsBtn === btn) {
        if (VoiceState.ttsState === 'speaking') { pauseSpeak(); return; }
        if (VoiceState.ttsState === 'paused') { resumeSpeak(); return; }
    }
    // 点了别的回答的朗读按钮 → 先把当前这条彻底停掉再开始
    stopSpeak();

    // 去掉 markdown 符号，纯文字朗读
    const plain = text
        .replace(/[*_`#>\[\]()]/g, '')
        .replace(/\s+/g, ' ')
        .trim();
    if (!plain) return;

    const u = new SpeechSynthesisUtterance(plain);
    u.lang = DIALECT_TTS_LANG[AppState.currentDialect] || 'zh-CN';
    u.rate = 0.95;

    VoiceState.ttsUtter = u;
    VoiceState.ttsBtn = btn;
    setTtsState('speaking', btn);

    // 只在「仍是当前这条 utterance」时才收尾，避免旧回调把新朗读的状态冲掉
    u.onend = function() { if (VoiceState.ttsUtter === u) stopSpeak(); };
    u.onerror = function() { if (VoiceState.ttsUtter === u) stopSpeak(); };

    window.speechSynthesis.speak(u);
    startTtsKeepAlive();
}

function pauseSpeak() {
    if (VoiceState.ttsState !== 'speaking') return;
    try { window.speechSynthesis.pause(); } catch (e) {}
    setTtsState('paused', VoiceState.ttsBtn);
}

function resumeSpeak() {
    if (VoiceState.ttsState !== 'paused') return;
    try { window.speechSynthesis.resume(); } catch (e) {}
    setTtsState('speaking', VoiceState.ttsBtn);
}

function stopSpeak() {
    stopTtsKeepAlive();
    if ('speechSynthesis' in window) {
        try { window.speechSynthesis.cancel(); } catch (e) {}
    }
    const btn = VoiceState.ttsBtn;
    VoiceState.ttsUtter = null;
    VoiceState.ttsState = 'idle';
    VoiceState.ttsBtn = null;
    if (btn) updateTtsBtn(btn, 'idle');
}

function setTtsState(state, btn) {
    VoiceState.ttsState = state;
    if (btn) updateTtsBtn(btn, state);
}

function updateTtsBtn(btn, state) {
    if (!btn) return;
    btn.classList.toggle('speaking', state === 'speaking');
    btn.classList.toggle('paused', state === 'paused');
    if (state === 'speaking') {
        btn.innerHTML = '<i class="fas fa-pause"></i> 暂停';
    } else if (state === 'paused') {
        btn.innerHTML = '<i class="fas fa-play"></i> 继续';
    } else {
        btn.innerHTML = '<i class="fas fa-volume-up"></i> 朗读';
    }
    // 停止按钮：仅在朗读中/暂停中显示
    const stopBtn = btn.parentElement ? btn.parentElement.querySelector('.voice-stop-btn') : null;
    if (stopBtn) stopBtn.style.display = (state === 'idle') ? 'none' : '';
}

// Chrome 对较长文本（约 15 秒以上）会「自动静默暂停」，需周期性 resume 维持朗读。
function startTtsKeepAlive() {
    stopTtsKeepAlive();
    VoiceState.ttsTimer = setInterval(function() {
        if (VoiceState.ttsState === 'speaking') {
            try { window.speechSynthesis.resume(); } catch (e) {}
        }
    }, 10000);
}
function stopTtsKeepAlive() {
    if (VoiceState.ttsTimer) { clearInterval(VoiceState.ttsTimer); VoiceState.ttsTimer = null; }
}

// ==================== 农业问答（对话式） ====================

const QAState = {
    // [{ question, answer, roundId, interrupted }]
    // 内存中保留的轮数多于实际送模型的轮数：多出来的部分只服务于
    // 「重新生成」按轮次定位（见 appendActions），不影响上下文长度。
    history: [],
    maxHistory: 10,
    isTyping: false,
    product: '',          // 当前对话所属作物，用于检测「切了作物但对话没换」
    abort: null,          // 在途请求的 AbortController，供「清空对话」中断
    generation: 0,        // 代次号：清空/切换作物时递增，使在途响应失效
    activeRound: null     // 当前在途轮次号：用于「忙碌态」的精确释放（代次号无法区分同代内的多轮）
};

const QA_QUESTION_MAXLEN = 500;        // 与后端 AGRI_QUESTION_MAX_LEN 一致
const QA_HISTORY_CONTEXT_TURNS = 5;    // 随请求送出的历史轮数，与后端 AGRI_HISTORY_MAX_TURNS 一致
const QA_REQUEST_TIMEOUT_MS = 60000;   // 非流式请求客户端超时（后端上游超时 30s）
const QA_STREAM_TIMEOUT_MS = 90000;    // 流式请求客户端超时

// 每轮问答一个标识，用于精确移除「某一轮」的气泡/按钮/建议，不依赖 DOM 顺序
let qaRoundSeq = 0;
function newQaRoundId() {
    qaRoundSeq += 1;
    return 'qa-r' + qaRoundSeq;
}

function setupAgricultureQA() {
    const askBtn = document.getElementById('ask-agriculture-btn');
    const questionInput = document.getElementById('agriculture-question');
    const clearBtn = document.getElementById('qa-clear-btn');

    // 前端长度上限与后端保持一致（后端仍会独立校验，前端只是提前拦截）
    if (questionInput) questionInput.setAttribute('maxlength', String(QA_QUESTION_MAXLEN));

    askBtn?.addEventListener('click', () => submitAgricultureQuestion());

    questionInput?.addEventListener('keydown', e => {
        // 中文输入法候选未上屏时，Enter 属于「选字」，不能当成发送
        if (e.isComposing || e.keyCode === 229) return;
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            askBtn?.click();
        }
    });

    // 自动调整文本框高度
    questionInput?.addEventListener('input', () => autoResizeTextarea(questionInput));

    clearBtn?.addEventListener('click', () => {
        resetQaConversation();
        showNotification('对话已清空', 'info');
    });

    // 示例问题（动态 + 静态混合）
    bindSuggestionClicks();

    // 切换作物时同步：对话本身属于上一个作物的语境，必须一并重置，
    // 否则旧作物的问答会被当作新作物的上下文一起发给模型，导致答非所问。
    document.querySelectorAll('.product-card').forEach(card => {
        card.addEventListener('click', () => syncQaProduct());
    });

    // 首屏：与已保存/已选作物保持一致（此前这些函数在初始化时从未被调用，
    // 导致欢迎语与示例问题固定停留在「荔枝」）
    QAState.product = AppState.currentProduct;
    updateProductLabel();
    refreshSuggestions(AppState.currentProduct);
}

// 统一提问入口：负责取值、长度校验、清空输入框，再交给 askAgricultureQuestion
function submitAgricultureQuestion(rawQuestion) {
    const input = document.getElementById('agriculture-question');
    const question = String(rawQuestion == null ? (input ? input.value : '') : rawQuestion).trim();
    if (!question) return;
    // 上一轮还在生成时不再静默丢弃：明确告知，避免「点了没反应」
    if (QAState.isTyping) {
        showNotification('正在回答上一个问题，请稍候再问', 'info');
        return;
    }
    if (question.length > QA_QUESTION_MAXLEN) {
        showNotification(`问题过长，请控制在 ${QA_QUESTION_MAXLEN} 字以内`, 'warning');
        return;
    }
    if (input) {
        input.value = '';
        autoResizeTextarea(input);
    }
    askAgricultureQuestion(question);
}

// 作物变化时重置对话。返回是否真的发生了切换。
function syncQaProduct() {
    const product = AppState.currentProduct;
    if (product === QAState.product) return false;
    QAState.product = product;
    resetQaConversation();
    refreshSuggestions(product);
    showNotification(`已切换到「${getProductName(product)}」，对话已重置`, 'info');
    return true;
}

// 重置对话：中断在途请求、清空历史与界面。既用于「清空对话」，也用于切换作物。
function resetQaConversation() {
    QAState.generation += 1;
    if (QAState.abort) {
        try { QAState.abort.abort(); } catch (e) { /* 忽略重复中断 */ }
        QAState.abort = null;
    }
    QAState.history = [];
    QAState.isTyping = false;
    QAState.activeRound = null;
    setQaBusy(false);
    clearChatFlow();
}

function setQaBusy(busy) {
    const askBtn = document.getElementById('ask-agriculture-btn');
    if (askBtn) {
        askBtn.disabled = !!busy;
        askBtn.setAttribute('aria-busy', busy ? 'true' : 'false');
    }
    // 提问进行中：示例问题与追问建议一并置灰。
    // 此前它们仍显示为可点击，点击后被 submitAgricultureQuestion 静默忽略，
    // 用户会以为「点了没反应」。
    document.querySelectorAll('.example-btn, .qa-action-btn.suggest-btn').forEach(btn => {
        btn.disabled = !!busy;
    });
    const input = document.getElementById('agriculture-question');
    if (input) input.setAttribute('aria-busy', busy ? 'true' : 'false');
}

function autoResizeTextarea(el) {
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 100) + 'px';
}

// 作物 id → 中文名（8 个，与顶部「选择农产品」/ 后端 EC_PRODUCTS 白名单一致）。
// 2026-10-05 从 getProductName 内联 map 抽出：直播间商品下拉(#live-product)也用它渲染。
const PRODUCT_NAMES = {
    lychee: '荔枝', longan: '龙眼', citrus: '柑橘', banana: '香蕉',
    aquatic: '水产养殖', rice: '水稻', tea: '茶叶', vegetable: '蔬菜',
};

function getProductName(productId) {
    return PRODUCT_NAMES[productId] || '广东特色农产品';
}

function updateProductLabel() {
    const label = document.getElementById('qa-product-label');
    if (label) label.textContent = getProductName(AppState.currentProduct);
}

// 恢复欢迎语。保留 id="qa-product-label"，否则清空后标签就再也找不到了。
function clearChatFlow() {
    const flow = document.getElementById('qa-chat-flow');
    if (!flow) return;
    flow.innerHTML = `
        <div class="qa-welcome">
            <i class="fas fa-robot"></i>
            <p>你好！我是AI农技专家，专注于<strong id="qa-product-label">${escapeHtml(getProductName(AppState.currentProduct))}</strong>种植指导。有什么问题尽管问我！</p>
        </div>
    `;
}

function bindSuggestionClicks() {
    const container = document.getElementById('qa-suggestions');
    if (!container) return;
    container.addEventListener('click', e => {
        const btn = e.target.closest('.example-btn');
        if (!btn) return;
        // 保持「点击即发送」的语义（目标用户是农户，减少一次点击），
        // 但统一走 submitAgricultureQuestion，以便共用长度与空值校验。
        submitAgricultureQuestion(btn.dataset.question || btn.textContent || '');
    });
}

// 建议栏兜底模板：接口不可达时使用，保证按钮与当前作物标签一致（{p} 为作物名）
const QA_GENERIC_QUESTIONS = [
    '{p}当前季节该做哪些管理？',
    '{p}常见病虫害如何防治？',
    '{p}怎么提高产量和品质？'
];

function renderGenericSuggestions(container, product) {
    const name = getProductName(product);
    container.dataset.product = product;
    container.innerHTML = '';
    QA_GENERIC_QUESTIONS.forEach(tpl => {
        const text = tpl.replace('{p}', name);
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'example-btn';
        btn.dataset.question = text;
        btn.textContent = text;
        btn.title = text;
        container.appendChild(btn);
    });
}

async function refreshSuggestions(product) {
    const container = document.getElementById('qa-suggestions');
    if (!container) return;

    let list = [];
    try {
        const data = await apiCall(`/api/agriculture/suggestions?product=${encodeURIComponent(product)}`);
        list = (data && data.success && Array.isArray(data.suggestions)) ? data.suggestions : [];
    } catch (e) {
        list = [];
    }

    // 拿不到建议时不能无条件保留旧按钮：若旧按钮属于「上一个作物」，
    // 就会出现「标签写着水稻、示例问题还在问荔枝」的自相矛盾。
    // 只在按钮确实属于当前作物时才保留。
    if (list.length === 0) {
        if (container.dataset.product !== product) renderGenericSuggestions(container, product);
        return;
    }

    // 用 DOM API 构建，data-question 走属性赋值，不存在 HTML/属性注入
    container.dataset.product = product;
    container.innerHTML = '';
    list.forEach(item => {
        const text = String(item);
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'example-btn';
        btn.dataset.question = text;
        btn.textContent = text;
        btn.title = text;
        container.appendChild(btn);
    });
}

function appendMessage(role, content, roundId) {
    const flow = document.getElementById('qa-chat-flow');
    if (!flow) return null;

    // 移除欢迎信息
    const welcome = flow.querySelector('.qa-welcome');
    if (welcome) welcome.remove();

    const div = document.createElement('div');
    div.className = `qa-message ${role}`;
    if (roundId) {
        div.dataset.qaRound = roundId;
        div.dataset.qaRole = role;
    }

    if (role === 'user') {
        div.innerHTML = `
            <div class="msg-avatar"><i class="fas fa-user"></i></div>
            <div class="msg-bubble">${escapeHtml(content)}</div>
        `;
    } else {
        div.innerHTML = `
            <div class="msg-avatar"><i class="fas fa-robot"></i></div>
            <div class="msg-bubble"><div class="msg-content"></div></div>
        `;
    }

    flow.appendChild(div);
    flow.scrollTop = flow.scrollHeight;
    return div;
}

function qaContentEl(msgEl) {
    return msgEl ? msgEl.querySelector('.msg-content') : null;
}

// 只移除某一轮的「输出」（机器人气泡 + 操作按钮 + 追问建议），保留用户提问气泡。
// 用于流式失败后回退到非流式，此时用户气泡必须留着，否则会被重复创建一次。
function removeQaBotOutput(roundId) {
    const flow = document.getElementById('qa-chat-flow');
    if (!flow || !roundId) return;
    flow.querySelectorAll(`[data-qa-round="${roundId}"]`).forEach(el => {
        if (el.dataset.qaRole !== 'user') el.remove();
    });
}

// 移除整轮（含用户提问气泡）。用于「重新生成」：随后重新提问会重建提问气泡，
// 避免旧气泡残留导致同一个问题在界面上出现两次。
function removeQaRound(roundId) {
    const flow = document.getElementById('qa-chat-flow');
    if (!flow || !roundId) return;
    flow.querySelectorAll(`[data-qa-round="${roundId}"]`).forEach(el => el.remove());
}

function appendTypingIndicator() {
    const flow = document.getElementById('qa-chat-flow');
    if (!flow) return null;
    const div = document.createElement('div');
    div.className = 'qa-message bot';
    div.id = 'qa-typing-indicator';
    div.innerHTML = `
        <div class="msg-avatar"><i class="fas fa-robot"></i></div>
        <div class="qa-typing">
            <div class="qa-typing-dots"><span></span><span></span><span></span></div>
            <span>思考中...</span>
        </div>
    `;
    flow.appendChild(div);
    flow.scrollTop = flow.scrollHeight;
    return div;
}

function removeTypingIndicator() {
    document.getElementById('qa-typing-indicator')?.remove();
}

function appendSuggestions(suggestions, roundId) {
    const flow = document.getElementById('qa-chat-flow');
    if (!flow || !Array.isArray(suggestions) || suggestions.length === 0) return null;

    const div = document.createElement('div');
    div.className = 'qa-msg-suggestions';
    if (roundId) {
        div.dataset.qaRound = roundId;
        div.dataset.qaRole = 'suggestions';
    }

    const bar = document.createElement('div');
    bar.className = 'qa-msg-actions';
    bar.style.marginTop = '4px';

    suggestions.forEach(item => {
        const text = String(item);
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'qa-action-btn suggest-btn';
        // 用 dataset 赋值而非拼字符串：进不了 HTML 解析，属性也无法被引号破坏
        btn.dataset.question = text;
        const icon = document.createElement('i');
        icon.className = 'fas fa-reply';
        btn.appendChild(icon);
        btn.appendChild(document.createTextNode(' ' + text));
        btn.addEventListener('click', () => submitAgricultureQuestion(text));
        bar.appendChild(btn);
    });

    div.appendChild(bar);
    flow.appendChild(div);
    flow.scrollTop = flow.scrollHeight;
    return div;
}

function appendActions(answer, roundId) {
    const flow = document.getElementById('qa-chat-flow');
    if (!flow) return null;

    const div = document.createElement('div');
    div.className = 'qa-msg-actions';
    if (roundId) {
        div.dataset.qaRound = roundId;
        div.dataset.qaRole = 'actions';
    }
    div.innerHTML = `
        <button class="qa-action-btn copy-btn"><i class="fas fa-copy"></i> 复制</button>
        <button class="qa-action-btn retry-btn"><i class="fas fa-redo"></i> 重新生成</button>
    `;
    flow.appendChild(div);

    div.querySelector('.copy-btn')?.addEventListener('click', function() {
        const btn = this;
        if (!navigator.clipboard) {
            showNotification('当前浏览器不支持自动复制，请手动选择文本', 'warning');
            return;
        }
        navigator.clipboard.writeText(answer).then(() => {
            btn.classList.add('copied');
            btn.innerHTML = '<i class="fas fa-check"></i> 已复制';
            setTimeout(() => {
                btn.classList.remove('copied');
                btn.innerHTML = '<i class="fas fa-copy"></i> 复制';
            }, 2000);
        }).catch(() => showNotification('复制失败，请手动选择文本', 'warning'));
    });

    // 「重新生成」：按轮次标识精确定位，不再假设「最后一个气泡就是刚生成的那条」。
    // 该轮若已滑出历史窗口，则从界面上取回原问题——此前会直接 return，
    // 表现为「点了重新生成毫无反应」。
    div.querySelector('.retry-btn')?.addEventListener('click', () => {
        if (QAState.isTyping) {
            showNotification('正在回答上一个问题，请稍候', 'info');
            return;
        }
        const idx = QAState.history.findIndex(h => h.roundId === roundId);
        let question = idx >= 0 ? QAState.history[idx].question : '';
        if (idx >= 0) QAState.history.splice(idx, 1);
        if (!question) {
            const bubble = document.querySelector(
                `[data-qa-round="${roundId}"][data-qa-role="user"] .msg-bubble`);
            question = bubble ? String(bubble.textContent || '').trim() : '';
        }
        if (!question) {
            showNotification('无法取回原问题，请重新输入', 'warning');
            return;
        }
        removeQaRound(roundId);
        askAgricultureQuestion(question);
    });

    flow.scrollTop = flow.scrollHeight;
    return div;
}

async function askAgricultureQuestion(question) {
    if (QAState.isTyping) return;
    const q = String(question || '').trim();
    if (!q) return;
    if (q.length > QA_QUESTION_MAXLEN) {
        showNotification(`问题过长，请控制在 ${QA_QUESTION_MAXLEN} 字以内`, 'warning');
        return;
    }

    // 作物若已变化，先重置对话，避免用上一个作物的上下文回答新作物的问题
    syncQaProduct();

    const generation = QAState.generation;
    QAState.isTyping = true;
    setQaBusy(true);

    const roundId = newQaRoundId();
    QAState.activeRound = roundId;
    appendMessage('user', q, roundId);

    try {
        const outcome = await askAgricultureStreaming(q, roundId, generation);
        // 仅当「流式通道本身不可用」时才回退到一次性请求，避免同一失败重试两次
        if (outcome === 'fallback') {
            await askAgricultureOnce(q, roundId, generation);
        }
    } finally {
        // 按轮次号释放：流式可能已在 done 事件处提前收尾并释放过，
        // 这里只兜底；若期间用户已开始新一轮，则不覆盖新一轮的忙碌态。
        if (QAState.activeRound === roundId) {
            QAState.activeRound = null;
            QAState.isTyping = false;
            setQaBusy(false);
        }
    }
}

// 非流式一次性请求（流式不可用时的回退路径）
async function askAgricultureOnce(question, roundId, generation) {
    // 已作废的轮次不再插入「思考中…」：此前该指示器在代次校验之前插入，
    // 一旦这轮被清空/切作物作废，它会残留在新一轮的对话里。
    if (generation !== QAState.generation) return;

    appendTypingIndicator();

    const result = await qaPostJson('/api/agriculture/ask', {
        question,
        product: AppState.currentProduct,
        history: qaHistoryPayload()
    }, QA_REQUEST_TIMEOUT_MS);

    removeTypingIndicator();
    if (generation !== QAState.generation) return;

    const data = result.data;
    if (!result.ok || !data || !data.success || !data.answer) {
        const message = (data && data.message)
            || (result.timedOut ? '请求超时，请重试'
                : result.aborted ? '请求已取消'
                    : qaStatusMessage(result.status));
        renderQaError(roundId, message, question);
        return;
    }

    const answer = String(data.answer);
    const msg = appendMessage('bot', '', roundId);
    const contentEl = qaContentEl(msg);
    // 回退路径直接渲染（渐进打字效果由正常情况下的流式路径提供）
    if (contentEl) contentEl.innerHTML = formatAnswer(answer);

    finishQaRound(roundId, question, answer, data.suggestions);
}

// 一轮问答的统一收尾：写历史 → 挂操作按钮 → 再挂本轮追问建议 → 刷新底部建议。
// 固定「按钮在前、建议在后」，流式与一次性两条路径共用同一顺序，
// 此前流式把建议插在循环里、按钮在循环后，两条路径的 DOM 顺序不一致。
function finishQaRound(roundId, question, answer, suggestions, opts) {
    const options = opts || {};
    QAState.history.push({
        question,
        answer,
        roundId,
        // 中断的半截回答不能当作完整答复回送给模型（见 qaHistoryPayload）
        interrupted: !!options.interrupted
    });
    while (QAState.history.length > QAState.maxHistory) QAState.history.shift();
    appendActions(answer, roundId);
    if (Array.isArray(suggestions) && suggestions.length > 0) {
        appendSuggestions(suggestions, roundId);
    }
    refreshSuggestions(AppState.currentProduct);
}

// 送给模型的历史上下文：中断轮次只保留提问、把回答置空。
// 后端 _build_agri_messages 会跳过 answer 为空的历史项，
// 从而避免「半截回答」被模型当成完整答复继续接龙。
function qaHistoryPayload() {
    return QAState.history.slice(-QA_HISTORY_CONTEXT_TURNS).map(h => ({
        question: h.question,
        answer: h.interrupted ? '' : h.answer
    }));
}

function qaStatusMessage(status) {
    if (status === 429) return '提问过于频繁，请稍后再试';
    if (status === 400) return '请求有误，请检查输入后重试';
    return 'AI 服务暂时不可用，请稍后重试';
}

// 在气泡位置渲染「可重试的错误态」，而不是把失败伪装成一条正常回答
function renderQaError(roundId, message, question) {
    removeQaBotOutput(roundId);
    const msg = appendMessage('bot', '', roundId);
    if (!msg) return;
    msg.classList.add('qa-message-error');
    const contentEl = qaContentEl(msg);
    if (!contentEl) return;
    showErrorState(contentEl, message, () => {
        removeQaRound(roundId);
        askAgricultureQuestion(question);
    });
}

// 带超时与会话头的 JSON POST。错误响应也把 body 解析出来，以便展示服务端给的 message。
// 全部异常都在内部收敛为返回值，调用方不需要 try/catch。
async function qaPostJson(path, body, timeoutMs) {
    const controller = ('AbortController' in window) ? new AbortController() : null;
    QAState.abort = controller;
    let timedOut = false;
    const timer = controller ? setTimeout(() => {
        timedOut = true;
        try { controller.abort(); } catch (e) { /* 忽略重复中断 */ }
    }, timeoutMs) : null;

    try {
        const headers = { 'Content-Type': 'application/json' };
        if (AppState.sessionId) headers['X-Session-Id'] = AppState.sessionId;
        const resp = await fetch(`${API_BASE_URL}${path}`, {
            method: 'POST',
            headers,
            signal: controller ? controller.signal : undefined,
            body: JSON.stringify(body)
        });
        let data = null;
        try { data = await resp.json(); } catch (e) { data = null; }
        return { ok: resp.ok, status: resp.status, data, aborted: false, timedOut: false };
    } catch (e) {
        return { ok: false, status: 0, data: null, aborted: true, timedOut };
    } finally {
        if (timer) clearTimeout(timer);
        if (QAState.abort === controller) QAState.abort = null;
    }
}

// ==================== SSE 流式 AI 问答 ====================

// 返回值：'done' 已渲染完成 ｜ 'fallback' 未渲染任何内容、调用方改用非流式 ｜ 'error' 已渲染错误态
async function askAgricultureStreaming(question, roundId, generation) {
    const controller = ('AbortController' in window) ? new AbortController() : null;
    QAState.abort = controller;

    // 看门狗：连接卡住时（read() 永不返回）也能真正超时，而不是干等
    let timedOut = false;
    let watchdog = null;
    const armWatchdog = () => {
        if (watchdog) clearTimeout(watchdog);
        watchdog = setTimeout(() => {
            timedOut = true;
            try { controller.abort(); } catch (e) { /* 忽略 */ }
        }, QA_STREAM_TIMEOUT_MS);
    };
    const clearWatchdog = () => {
        if (watchdog) clearTimeout(watchdog);
        watchdog = null;
        if (QAState.abort === controller) QAState.abort = null;
    };

    let response;
    try {
        armWatchdog();
        response = await fetch(`${API_BASE_URL}/api/agriculture/ask/stream`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...(AppState.sessionId ? { 'X-Session-Id': AppState.sessionId } : {})
            },
            signal: controller ? controller.signal : undefined,
            body: JSON.stringify({
                question,
                product: AppState.currentProduct,
                history: qaHistoryPayload()
            })
        });
    } catch (e) {
        clearWatchdog();
        if (generation !== QAState.generation) return 'error';
        console.warn('SSE 连接未能建立，改用一次性请求:', e && e.message);
        return 'fallback';
    }

    if (!response.ok) {
        clearWatchdog();
        if (generation !== QAState.generation) return 'error';
        // 服务端对「未启用 / 限流 / 参数错」都会给出明确 message，直接呈现即可；
        // 不在这里再走一次非流式（同一原因必然再次失败，白白多一次往返）。
        let data = null;
        try { data = await response.json(); } catch (e) { data = null; }
        if (data && data.message) {
            renderQaError(roundId, data.message, question);
            return 'error';
        }
        // 只有「流式端点本身不存在」才值得回退到一次性请求
        if (response.status === 404 || response.status === 405) return 'fallback';
        renderQaError(roundId, qaStatusMessage(response.status), question);
        return 'error';
    }
    if (!response.body) {
        clearWatchdog();
        return 'fallback';
    }
    // 响应到达前若已被「清空对话 / 切换作物」作废，就不要往界面上插新气泡
    if (generation !== QAState.generation) {
        clearWatchdog();
        return 'error';
    }

    const msg = appendMessage('bot', '', roundId);
    const contentEl = qaContentEl(msg);
    const flow = document.getElementById('qa-chat-flow');
    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    let buffer = '';
    let fullAnswer = '';
    let streamError = '';
    let sawEvent = false;         // 是否解析出过任何 SSE 事件：区分「通道不通」与「上游失败」
    let pendingSuggestions = [];  // done 之前到达的追问建议，随收尾一起挂出
    let finalized = false;

    // 释放「提问中」状态。按轮次判定，避免上一轮的收尾把新一轮的忙碌态清掉。
    const releaseBusy = () => {
        if (QAState.activeRound !== roundId) return;
        QAState.activeRound = null;
        QAState.isTyping = false;
        setQaBusy(false);
    };

    // 统一收尾：渲染正文 → 写历史 → 挂操作按钮 → 再挂本轮追问建议。
    const finalize = (answer, opts) => {
        if (finalized || generation !== QAState.generation) return false;
        finalized = true;
        if (contentEl) contentEl.innerHTML = formatAnswer(answer)
            + (opts && opts.interrupted ? qaInterruptNoteHtml() : '');
        finishQaRound(roundId, question, answer, pendingSuggestions, opts);
        pendingSuggestions = [];
        releaseBusy();
        return true;
    };

    try {
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            armWatchdog();
            buffer += decoder.decode(value, { stream: true });

            // 按空行切分完整 SSE 块：一个块里的 event 与 data 必须一起解析，
            // 否则 error 事件与其 message 会被拆散
            let sep;
            while ((sep = buffer.indexOf('\n\n')) !== -1) {
                const block = buffer.slice(0, sep);
                buffer = buffer.slice(sep + 2);
                if (!block.trim()) continue;
                sawEvent = true;

                const parsed = parseSseBlock(block);
                if (parsed.event === 'error') {
                    // 错误类型以服务端下发的 code 为准，不再靠中文文案正则猜测
                    const errPayload = ssePayload(parsed.data);
                    streamError = (errPayload && errPayload.message)
                        || 'AI 服务暂时不可用，请稍后重试';
                    break;
                }
                if (parsed.event === 'done') {
                    // 正文已完整：立即收尾并放开输入框，不必等追问建议生成完。
                    // 此后仍继续读取，以便接住随后的 suggestions 事件。
                    finalize(fullAnswer);
                    continue;
                }
                if (parsed.event === 'suggestions') {
                    try {
                        const payload = JSON.parse(parsed.data);
                        const list = payload && payload.suggestions;
                        if (Array.isArray(list) && list.length && generation === QAState.generation) {
                            // 已收尾则直接挂出（按钮仍在前）；未收尾则并入收尾时一起挂
                            if (finalized) appendSuggestions(list, roundId);
                            else pendingSuggestions = pendingSuggestions.concat(list);
                        }
                    } catch (e) { /* 忽略结构异常的建议 */ }
                    continue;
                }
                try {
                    const payload = JSON.parse(parsed.data);
                    if (payload && typeof payload.content === 'string' && payload.content) {
                        fullAnswer += payload.content;
                        if (contentEl) contentEl.innerHTML = formatAnswer(fullAnswer);
                        if (flow) flow.scrollTop = flow.scrollHeight;
                    }
                } catch (e) { /* 跳过无法解析的数据块 */ }
            }
            if (streamError) break;
        }
    } catch (e) {
        streamError = timedOut
            ? 'AI 响应超时，请重试'
            : (e && e.name === 'AbortError' ? '请求已取消' : 'AI 服务连接中断，请重试');
    } finally {
        clearWatchdog();
        try { reader.cancel(); } catch (e) { /* 忽略 */ }
    }

    // 已被「清空对话 / 切换作物」作废：丢弃结果，绝不写入界面
    if (generation !== QAState.generation) return 'error';

    // 正文已在 done 事件处收尾：此后（追问建议阶段）的连接中断不影响本轮结果
    if (finalized) return 'done';

    if (streamError) {
        if (fullAnswer.trim()) {
            // 已经流出的内容保留，把中断原因补在气泡内，避免整段回答凭空消失
            finalize(fullAnswer, { interrupted: true });
        } else {
            // 上游已经报错：再走一次非流式必然同样失败，只会让用户多等一个超时
            removeQaBotOutput(roundId);
            renderQaError(roundId, streamError, question);
        }
        return 'error';
    }

    // 上游「成功但没有任何内容」也是失败，绝不能留下一个空气泡
    if (!fullAnswer.trim()) {
        removeQaBotOutput(roundId);
        // 一个事件都没收到 → 流式通道不通（代理缓冲/截断），值得回退到一次性请求；
        // 收到过事件却始终没有正文 → 上游确实没产出，直接呈现错误态，不再重试一次。
        if (!sawEvent) return 'fallback';
        renderQaError(roundId, 'AI 服务未返回内容，请重试', question);
        return 'error';
    }

    finalize(fullAnswer);
    return 'done';
}

// 极简 SSE 块解析：一个块内可能同时存在 event 行与 data 行
function parseSseBlock(block) {
    let event = 'message';
    const dataLines = [];
    block.split('\n').forEach(line => {
        if (line.indexOf('event:') === 0) {
            event = line.slice(6).trim();
        } else if (line.indexOf('data:') === 0) {
            dataLines.push(line.slice(5).replace(/^ /, ''));
        }
    });
    return { event, data: dataLines.join('\n') };
}

// 解析 SSE 的 data 段为对象。错误事件里同时带 code 与 message，
// 调用方按 code 判定类型，不再依赖 message 的中文措辞。
function ssePayload(data) {
    try {
        const payload = JSON.parse(data);
        return (payload && typeof payload === 'object') ? payload : null;
    } catch (e) {
        return null;
    }
}

function qaInterruptNoteHtml() {
    return '<div class="qa-inline-note">回答在中途中断，以上为已生成的内容。</div>';
}

function formatAnswer(text) {
    // 关键：先整体转义，再套格式。
    // 否则模型输出里的 < & 等会被浏览器当成 HTML 解析（此前的实现存在注入面）。
    const safe = escapeHtml(String(text == null ? '' : text));
    return safe
        .replace(/\*\*([\s\S]+?)\*\*/g, '<strong>$1</strong>')
        .replace(/\n/g, '<br>')
        // 只把「行首的编号」当列表项；负向断言排除 "3.5"、"10.5公斤" 这类小数被误断行
        .replace(/(^|<br>)\s*(\d{1,2})[.、](?!\d)\s*/g, '$1$2. ')
        .replace(/(^|<br>)\s*[-•·]\s+/g, '$1- ');
}

// ==================== 农时日历 ====================

// 任务分类配色（与后端 tasks[].category 对应）
const FARMING_CATEGORY_COLORS = {
    fertilize: '#1f5e43',
    pest: '#ef4444',
    harvest: '#d9a227',
    manage: '#4a6fa5',
    water: '#4a8a6a'
};

// 当前渲染的日历接口数据（供格子点击弹窗复用）
let farmingCalendarData = null;
// 并发请求序号，避免快速翻月时旧响应覆盖新响应
let farmingCalendarReqSeq = 0;
// 当前用户已订阅的作物 id 列表（供「订阅提醒」摘要条同步显示，不依赖全站通知链路）
let farmingSubscribedIds = [];

function setupCalendar() {
    document.getElementById('prev-month')?.addEventListener('click', () => {
        AppState.calendarMonth = (AppState.calendarMonth + 11) % 12;
        updateFarmingCalendar();
    });

    document.getElementById('next-month')?.addEventListener('click', () => {
        AppState.calendarMonth = (AppState.calendarMonth + 1) % 12;
        updateFarmingCalendar();
    });

    document.getElementById('farming-subscribe-btn')?.addEventListener('click', toggleFarmingSubscription);

    // 展开/收起「数据依据」来源清单
    document.getElementById('farming-date-notice-toggle')?.addEventListener('click', function () {
        const listEl = document.getElementById('farming-date-notice-sources');
        if (!listEl) return;
        const hidden = listEl.classList.toggle('is-hidden');
        this.setAttribute('aria-expanded', hidden ? 'false' : 'true');
    });

    updateFarmingCalendar();
    syncFarmingSubscriptionButton();
}

async function updateFarmingCalendar() {
    const calendarGrid = document.getElementById('calendar-grid');
    const taskList = document.getElementById('farming-task-list');
    if (!calendarGrid) return;

    const month = AppState.calendarMonth;              // 0-indexed
    const product = AppState.currentProduct || 'lychee';
    const monthLabel = document.getElementById('current-month');

    if (monthLabel) monthLabel.textContent = `${month + 1}月`;

    // 加载态（避免请求期间白屏）
    calendarGrid.innerHTML = '<div class="calendar-loading">农事数据加载中…</div>';
    if (taskList) showSkeleton(taskList, 'row', 2);

    const seq = ++farmingCalendarReqSeq;
    let data;
    try {
        // 不传 year：由后端按服务器当前年计算节气（年周期模板，逐年复现）
        data = await apiCall(`/api/agriculture/calendar/${encodeURIComponent(product)}?month=${month + 1}`);
    } catch (e) {
        if (seq !== farmingCalendarReqSeq) return;
        farmingCalendarData = null;
        hideFarmingNotices();
        showErrorState(calendarGrid, '农事数据加载失败，请重试', () => updateFarmingCalendar());
        if (taskList) showErrorState(taskList, '农事数据加载失败，请重试', () => updateFarmingCalendar());
        return;
    }
    if (seq !== farmingCalendarReqSeq) return;          // 已有更新的请求，丢弃本次
    if (!data || !data.success) {
        farmingCalendarData = null;
        hideFarmingNotices();
        showErrorState(calendarGrid, (data && data.message) || '农事数据加载失败，请重试', () => updateFarmingCalendar());
        if (taskList) taskList.innerHTML = '';
        return;
    }
    farmingCalendarData = data;

    // 数据依据入口：仅在有来源可列时挂出，点击展开该作物全年来源方向（不放说明性文案）
    renderFarmingDateNotice(data);

    const year = data.year;
    const firstDay = new Date(year, month, 1).getDay();
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const today = new Date();

    // 按日聚合：节气 + 任务
    const termByDay = {};
    (data.solar_terms || []).forEach(t => { termByDay[t.day] = t.name; });
    const tasksByDay = {};
    (data.tasks || []).forEach(t => {
        if (t.day) (tasksByDay[t.day] = tasksByDay[t.day] || []).push(t);
    });
    const datedCount = (data.tasks || []).filter(t => t.day).length;
    const undatedCount = (data.tasks || []).filter(t => !t.day).length;

    let html = '';
    ['日', '一', '二', '三', '四', '五', '六'].forEach(d => {
        html += `<div class="calendar-header">${d}</div>`;
    });
    for (let i = 0; i < firstDay; i++) html += '<div class="calendar-day is-blank"></div>';

    for (let d = 1; d <= daysInMonth; d++) {
        const dayTasks = tasksByDay[d] || [];
        const isToday = (d === today.getDate() && month === today.getMonth() && year === today.getFullYear());
        const cls = ['calendar-day'];
        if (dayTasks.length) cls.push('is-clickable');
        if (isToday) cls.push('today');

        const dots = dayTasks.slice(0, 3).map(t =>
            `<span class="day-dot" style="background:${FARMING_CATEGORY_COLORS[t.category] || '#4a6fa5'}"></span>`
        ).join('');
        const term = termByDay[d] ? `<span class="lunar-marker">${escapeHtml(termByDay[d])}</span>` : '';

        html += `<div class="${cls.join(' ')}"${dayTasks.length ? ` data-day="${d}" role="button" tabindex="0" aria-label="${d}日，${dayTasks.length}项农事"` : ''}>`
              + `<span class="day-num">${d}</span>`
              + (dots ? `<span class="day-dots">${dots}</span>` : '')
              + term
              + `</div>`;
    }
    // 整月只有持续性作业（无固定日期）：格子层给出明确说明，避免「一片空白」被误读为数据缺失
    if (datedCount === 0 && undatedCount > 0) {
        html += '<div class="calendar-blank-notice">'
              + '<strong>本月无固定日期农事</strong><br>'
              + `该作物本月为持续性作业（如水分管理），共 ${undatedCount} 项，详见右侧「本月农事要点」。`
              + '</div>';
    }
    if (!calendarGrid) return;
    calendarGrid.innerHTML = html;

    // 物候期主题色：注入 CSS 变量供格子与色条使用
    const phase = data.phenophase_current;
    if (phase && phase.color) {
        calendarGrid.style.setProperty('--phase-color', phase.color);
        calendarGrid.classList.add('has-phase');
    } else {
        calendarGrid.style.removeProperty('--phase-color');
        calendarGrid.classList.remove('has-phase');
    }
    renderPhenophaseBar(phase);

    // 格子点击 → 当日任务弹窗（键盘可达）
    calendarGrid.querySelectorAll('.calendar-day.is-clickable').forEach(cell => {
        const open = () => showDayTasksModal(parseInt(cell.dataset.day, 10));
        cell.addEventListener('click', open);
        cell.addEventListener('keydown', e => {
            if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(); }
        });
    });

    renderFarmingTaskList(taskList, data);
    renderFarmingReminderSummary(data);
}

// 加载失败时收起农时日历内的提示条，避免残留过期提示
function hideFarmingNotices() {
    document.getElementById('farming-date-notice')?.classList.add('is-hidden');
    document.getElementById('farming-reminder-summary')?.classList.add('is-hidden');
}

// 数据依据入口：点击可展开该作物全年用到的来源方向（机构 · 文件类型 · 文号）。
// 设计取舍：**不再放任何说明性句子**，只保留可展开的来源清单；
// 「日期为参考值」这层意思由日期标签的「约」前缀与当日弹窗的说明承担。
// 兜底：后端未返回 sources_all（如服务端仍是旧版本）时整条收起，避免出现「本月 0 项」这类伪计数。
function renderFarmingDateNotice(data) {
    const notice = document.getElementById('farming-date-notice');
    if (!notice) return;
    const toggle = document.getElementById('farming-date-notice-toggle');
    const listEl = document.getElementById('farming-date-notice-sources');

    if (!data || !data.success || !toggle || !listEl) {
        notice.classList.add('is-hidden');
        return;
    }

    const sources = data.sources_all || [];
    if (!sources.length) {
        notice.classList.add('is-hidden');
        listEl.innerHTML = '';
        listEl.classList.add('is-hidden');
        toggle.setAttribute('aria-expanded', 'false');
        return;
    }

    notice.classList.remove('is-hidden');
    toggle.classList.remove('is-hidden');
    // 来源清单按数量做一次渲染缓存，避免翻月时重建 DOM 导致已展开状态丢失
    if (listEl.dataset.rendered !== String(sources.length)) {
        listEl.innerHTML = sources.map(s => {
            const docNo = s.doc_no || '待核';
            const link = s.url
                ? ` <a href="${escapeHtml(s.url)}" target="_blank" rel="noopener noreferrer">查验</a>`
                : '';
            return `<li>`
                 + `<span class="fdn-src-name">${escapeHtml(s.name || '')}</span>`
                 + `<span class="fdn-src-meta">${escapeHtml(s.org || '')} · ${escapeHtml(s.doc_type || '')} · 文号：${escapeHtml(docNo)}${link}</span>`
                 + `</li>`;
        }).join('');
        listEl.dataset.rendered = String(sources.length);
        listEl.classList.add('is-hidden');
        toggle.setAttribute('aria-expanded', 'false');
    }
}

// 「订阅提醒」摘要条（农时日历内闭环）。
// 设计取舍：不写 AppState.currentUser、不动 updateBadgeCount / loadNotifications，
// 仅用当前已加载的日历数据 + 订阅状态在本区块内给出可见反馈，
// 让「订阅后按月收到提醒」这条决策在农时日历里有落点，同时不触碰全站通知链路。
function renderFarmingReminderSummary(data) {
    const box = document.getElementById('farming-reminder-summary');
    if (!box) return;
    if (!data || !data.success) { box.classList.add('is-hidden'); return; }

    const pid = (data.product && data.product.id) || AppState.currentProduct;
    const subscribed = farmingSubscribedIds.indexOf(pid) !== -1;
    const tasks = data.tasks || [];
    const urgent = tasks.filter(t => t.priority === 'high').length;

    if (!AppState.user) {
        box.classList.remove('is-hidden');
        box.innerHTML = `<i class="fas fa-bell"></i>`
            + `<span>登录后可订阅「<span class="frs-strong">${escapeHtml((data.product && data.product.name) || '')}</span>」，登录时会补发当月已到期的农事提醒。</span>`;
        return;
    }

    if (!subscribed) {
        box.classList.remove('is-hidden');
        box.innerHTML = `<i class="far fa-bell"></i>`
            + `<span>尚未订阅「<span class="frs-strong">${escapeHtml((data.product && data.product.name) || '')}</span>」。`
            + `点击右侧「订阅本作物」，登录时会补发当月已到期的农事提醒。</span>`;
        return;
    }

    box.classList.remove('is-hidden');
    box.innerHTML = `<i class="fas fa-bell"></i>`
        + `<span>已订阅「<span class="frs-strong">${escapeHtml((data.product && data.product.name) || '')}</span>」·`
        + `本月共 <span class="frs-strong">${tasks.length}</span> 项农事`
        + (urgent ? `，其中 <span class="frs-urgent">${urgent} 项紧急</span>` : '')
        + `。登录时会补发当月已到期的提醒，可在消息中心查看。</span>`;
}

function renderPhenophaseBar(phase) {
    const bar = document.getElementById('phenophase-bar');
    if (!bar) return;
    if (!phase) {
        bar.classList.add('is-hidden');
        bar.innerHTML = '';
        return;
    }
    bar.classList.remove('is-hidden');
    bar.style.setProperty('--phase-color', phase.color || '#1f5e43');
    bar.innerHTML = `<span class="phase-dot"></span>`
        + `<strong>当前物候期：${escapeHtml(phase.name)}</strong>`
        + (phase.description ? `<span class="phase-desc">${escapeHtml(phase.description)}</span>` : '');
}

// Font Awesome 类名归一化。
// 历史数据里的 icon 值（seedling / broom / apple-alt ...）不带 fa- 前缀，
// 直接拼成 class="fas seedling" 不会渲染出图标，这里统一补齐前缀。
// FA_ICON_ALIASES：修正 FA 6.0.0 Free 中不存在的图标名（已逐个核对，仅 fishing 缺失）。
const FA_ICON_ALIASES = {
    fishing: 'fish'
};

function faIconClass(name) {
    let n = String(name == null ? '' : name).trim() || 'tasks';
    if (n.indexOf('fa-') === 0) n = n.slice(3);
    n = FA_ICON_ALIASES[n] || n;
    return 'fa-' + n;
}

function farmingTaskItemHtml(t, idx) {
    const color = FARMING_CATEGORY_COLORS[t.category] || '#4a6fa5';
    // is_verified = 0 / 缺省 => 日期为按农时规律推算的参考值，加「约」并套提示色
    const approx = !t.is_verified;
    const timingTag = t.day
        ? `<span class="task-tag tag-timing${approx ? ' tag-approx' : ''}"${approx ? ' title="依据公开技术资料编排的参考日期，尚未经农技人员复核"' : ''}><i class="far fa-clock"></i> ${approx ? '约 ' : ''}${escapeHtml(t.date || (t.task_md || ''))}</span>`
        : `<span class="task-tag tag-timing"><i class="far fa-clock"></i> 持续性作业</span>`;
    // 依据等级角标：verified=已复核 / unsourced=无来源登记（不应出现，出现即暴露数据缺口）
    const evidenceTag = t.evidence_level === 'verified'
        ? '<span class="task-tag tag-verified"><i class="fas fa-circle-check"></i> 已复核</span>'
        : (t.evidence_level === 'unsourced'
            ? '<span class="task-tag tag-unsourced"><i class="fas fa-triangle-exclamation"></i> 来源待补</span>'
            : '');
    const src = t.source || null;
    const basisHtml = t.date_basis
        ? `<div class="task-basis"><span class="basis-label"><i class="fas fa-book-open"></i> 日期依据</span><p>${escapeHtml(t.date_basis)}</p></div>`
        : '';
    const sourceHtml = src
        ? `<div class="task-basis task-source"><span class="basis-label"><i class="fas fa-landmark"></i> 来源方向</span>`
          + `<p>${escapeHtml(src.org || '')} · ${escapeHtml(src.doc_type || '')} · ${escapeHtml(src.name || '')}`
          + `<span class="src-docno">文号：${escapeHtml(src.doc_no || '待核')}</span>`
          + (src.url ? ` <a href="${escapeHtml(src.url)}" target="_blank" rel="noopener noreferrer">查验</a>` : '')
          + '</p></div>'
        : '';
    return `
    <div class="task-item task-item-rich" style="--task-color: ${color}" data-idx="${idx}"${t.day ? ` data-day="${t.day}"` : ''}>
        <div class="task-header">
            <div class="task-icon-wrap" style="background: ${color}15; color: ${color}">
                <i class="fas ${faIconClass(t.icon)}"></i>
            </div>
            <div class="task-meta">
                <h5>${escapeHtml(t.title)}</h5>
                <div class="task-tags">
                    <span class="task-tag tag-category" style="background: ${color}18; color: ${color}">${escapeHtml(t.category_label || '')}</span>
                    ${t.priority === 'high' ? '<span class="task-tag tag-urgent"><i class="fas fa-fire"></i> 紧急</span>' : ''}
                    ${timingTag}
                    ${evidenceTag}
                </div>
            </div>
            <button class="task-expand-btn" aria-label="展开详情"><i class="fas fa-chevron-down"></i></button>
        </div>
        <p class="task-desc">${escapeHtml(t.description || '')}</p>
        <div class="task-detail">
            <div class="task-tips">
                <i class="fas fa-lightbulb"></i>
                <span>${escapeHtml(t.tip || '')}</span>
            </div>
            ${basisHtml}
            ${sourceHtml}
        </div>
    </div>`;
}

function renderFarmingTaskList(taskList, data) {
    if (!taskList) return;
    const tasks = data.tasks || [];
    if (!data.is_configured || !tasks.length) {
        showEmptyState(taskList, 'fa-calendar-times', '本月暂无农事数据', '该作物尚未录入本月的农事安排');
        return;
    }

    const dated = tasks.filter(t => t.day).sort((a, b) => a.day - b.day);
    const undated = tasks.filter(t => !t.day);

    let listHtml = '';
    if (dated.length) {
        listHtml += `<div class="task-group-label">本月已安排日期${data.dates_provisional ? '（依据公开技术资料编排，待复核）' : ''}</div>`;
        listHtml += dated.map(farmingTaskItemHtml).join('');
    }
    if (undated.length) {
        listHtml += `<div class="task-group-label">持续性作业（不指定日期）</div>`;
        listHtml += undated.map(farmingTaskItemHtml).join('');
    }
    taskList.innerHTML = listHtml;

    // 展开/折叠
    taskList.querySelectorAll('.task-expand-btn').forEach(btn => {
        btn.addEventListener('click', function () {
            this.closest('.task-item-rich')?.classList.toggle('expanded');
        });
    });

    // 点击列表项 → 滚动并高亮对应格子
    taskList.querySelectorAll('.task-item-rich[data-day]').forEach(item => {
        item.addEventListener('click', e => {
            if (e.target.closest('.task-expand-btn')) return;
            highlightCalendarDay(parseInt(item.dataset.day, 10));
        });
    });
}

function highlightCalendarDay(day) {
    const cell = document.querySelector(`#calendar-grid .calendar-day[data-day="${day}"]`);
    if (!cell) return;
    cell.classList.add('is-highlight');
    setTimeout(() => cell.classList.remove('is-highlight'), 1600);
    cell.scrollIntoView({ behavior: prefersReducedMotion ? 'auto' : 'smooth', block: 'nearest' });
}

// 格子点击 → 当日农事弹窗
function showDayTasksModal(day) {
    const data = farmingCalendarData;
    if (!data) return;
    const tasks = (data.tasks || []).filter(t => t.day === day);
    if (!tasks.length) return;

    const phase = data.phenophase_current;
    const productName = (data.product && data.product.name) || '';
    const anyApprox = tasks.some(t => !t.is_verified);
    const html = `
        <div class="day-task-modal">
            <div class="day-task-head">
                <strong>${data.month}月${day}日</strong>
                ${phase ? `<span class="day-task-phase" style="background:${phase.color}18;color:${phase.color}">${escapeHtml(phase.name)}</span>` : ''}
            </div>
            ${anyApprox ? '<div class="day-task-approx-note"><i class="fas fa-circle-info"></i> 该日期为依据公开技术资料编排的参考值，尚未经农技人员复核，请以当地农技站指导为准。</div>' : ''}
            ${tasks.map(t => {
                const color = FARMING_CATEGORY_COLORS[t.category] || '#4a6fa5';
                const src = t.source || null;
                const evTag = t.evidence_level === 'verified'
                    ? '<span class="task-tag tag-verified"><i class="fas fa-circle-check"></i> 已复核</span>'
                    : (t.evidence_level === 'unsourced'
                        ? '<span class="task-tag tag-unsourced"><i class="fas fa-triangle-exclamation"></i> 来源待补</span>'
                        : '');
                return `<div class="day-task-item" style="--task-color:${color}">
                    <div class="day-task-title">
                        <i class="fas ${faIconClass(t.icon)}" style="color:${color}"></i>
                        <span>${escapeHtml(t.title)}</span>
                        <span class="task-tag tag-category" style="background:${color}18;color:${color}">${escapeHtml(t.category_label || '')}</span>
                        ${evTag}
                    </div>
                    <p>${escapeHtml(t.description || '')}</p>
                    ${t.tip ? `<div class="task-tips"><i class="fas fa-lightbulb"></i><span>${escapeHtml(t.tip)}</span></div>` : ''}
                    ${t.date_basis ? `<div class="task-basis"><span class="basis-label"><i class="fas fa-book-open"></i> 日期依据</span><p>${escapeHtml(t.date_basis)}</p></div>` : ''}
                    ${src ? `<div class="task-basis task-source"><span class="basis-label"><i class="fas fa-landmark"></i> 来源方向</span><p>${escapeHtml(src.org || '')} · ${escapeHtml(src.doc_type || '')} · ${escapeHtml(src.name || '')}<span class="src-docno">文号：${escapeHtml(src.doc_no || '待核')}</span></p></div>` : ''}
                </div>`;
            }).join('')}
        </div>`;
    showDetailModal(`${productName} · ${data.month}月${day}日农事`, html);
}

// ==================== 农事订阅 ====================

function updateSubscribeButton(btn, subscribed, disabled) {
    btn.dataset.subscribed = subscribed ? '1' : '0';
    btn.classList.toggle('is-subscribed', !!subscribed);
    btn.innerHTML = subscribed
        ? '<i class="fas fa-star"></i> 已订阅'
        : '<i class="far fa-star"></i> 订阅本作物';
    if (disabled) {
        btn.setAttribute('title', '登录后可订阅农事提醒');
    } else {
        btn.removeAttribute('title');
    }
}

function syncFarmingSubscriptionButton() {
    const btn = document.getElementById('farming-subscribe-btn');
    if (!btn) return;
    if (!AppState.user) {
        farmingSubscribedIds = [];
        updateSubscribeButton(btn, false, true);
        renderFarmingReminderSummary(farmingCalendarData);
        return;
    }
    apiCall('/api/agriculture/subscriptions')
        .then(d => {
            const ids = (d && d.product_ids) || [];
            farmingSubscribedIds = ids;
            updateSubscribeButton(btn, ids.includes(AppState.currentProduct), false);
            renderFarmingReminderSummary(farmingCalendarData);
        })
        .catch(() => {
            farmingSubscribedIds = [];
            updateSubscribeButton(btn, false, false);
            renderFarmingReminderSummary(farmingCalendarData);
        });
}

async function toggleFarmingSubscription() {
    if (!AppState.user) {
        openLoginModal();
        showNotification('请先登录后再订阅农事提醒', 'info', { actionLabel: '去登录', action: openLoginModal });
        return;
    }
    const btn = document.getElementById('farming-subscribe-btn');
    const productId = AppState.currentProduct;
    const subscribed = btn?.dataset.subscribed === '1';
    try {
        if (subscribed) {
            await apiCall(`/api/agriculture/subscribe/${encodeURIComponent(productId)}`, 'DELETE');
            showNotification('已取消订阅', 'info');
        } else {
            await apiCall('/api/agriculture/subscribe', 'POST', { product_id: productId });
            showNotification('订阅成功，登录后会收到当月农事提醒', 'success');
        }
        syncFarmingSubscriptionButton();
    } catch (e) {
        showNotification('操作失败，请稍后重试', 'error');
    }
}

// 登录后拉取农事提醒（幂等，失败静默）
function checkFarmingReminders() {
    if (!AppState.sessionId) return;
    apiCall('/api/agriculture/reminders/check', 'POST').catch(() => {});
}

// ==================== 病虫害诊断入口（农业技能板块） ====================

function setupPestDiagnosisEntry() {
    // 诊断入口卡片点击：展开/收起诊断面板
    const entryCard = document.querySelector('.diagnosis-entry-card');
    const panel = document.getElementById('pest-diagnosis-area');
    const toggleBtn = document.getElementById('toggle-diagnosis');

    function togglePanel(show) {
        if (!panel) return;
        const willShow = show !== undefined ? show : panel.classList.contains('is-hidden');
        panel.classList.toggle('is-hidden', !willShow);
        if (willShow) {
            initPestDiagnosis();
            panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
            if (toggleBtn) toggleBtn.innerHTML = '<i class="fas fa-chevron-up"></i> 收起诊断面板';
        } else if (toggleBtn) {
            toggleBtn.innerHTML = '<i class="fas fa-chevron-down"></i> 展开诊断面板';
        }
    }

    entryCard?.addEventListener('click', () => togglePanel());
    toggleBtn?.addEventListener('click', (e) => {
        e.stopPropagation();
        togglePanel();
    });

    // 关闭按钮
    panel?.querySelector('.sim-close-btn')?.addEventListener('click', () => togglePanel(false));
}

// ==================== 病虫害诊断 ====================

// 与服务端约定保持一致：app.py 的 DIAG_SYMPTOMS_MAX_LEN / DIAG_MAX_IMAGES / DIAG_MAX_IMAGE_BYTES
const DIAG_SYMPTOMS_MAXLEN = 500;
const DIAG_MAX_IMAGES = 3;
const DIAG_MAX_IMAGE_BYTES = 4 * 1024 * 1024;
const DIAG_IMAGE_MAX_EDGE = 1280;      // 压缩后长边上限（像素）
const DIAG_IMAGE_QUALITY = 0.8;        // 压缩后 JPEG 质量

const PestState = {
    selectedCrop: 'lychee',
    initialized: false,
    images: [],             // 已选照片（本机压缩后的 jpeg data URL）
    busy: false,            // 在途请求标记，防止连点造成并发请求
    userSelectedCrop: false // 用户手动选过作物后，不再被农时日历同步覆盖
};

// 症状输入框示例文案按作物分流：水产养殖不是「叶片」场景
const DIAG_PLACEHOLDER_DEFAULT = '例如：叶片发黄，有褐色斑点，部分果实脱落...';
const DIAG_PLACEHOLDER_AQUATIC = '例如：虾体甲壳内侧出现白色斑点，游塘、反应迟钝...';

function updateDiagSymptomPlaceholder() {
    const box = document.getElementById('symptom-text');
    if (!box) return;
    // 用户已经输入内容时不打断，只更新示例
    box.placeholder = PestState.selectedCrop === 'aquatic'
        ? DIAG_PLACEHOLDER_AQUATIC
        : DIAG_PLACEHOLDER_DEFAULT;
}

function setDiagBusy(busy) {
    PestState.busy = busy;
    ['start-diagnosis', 'upload-photo-btn', 're-diagnose'].forEach(id => {
        const btn = document.getElementById(id);
        if (btn) btn.disabled = busy;
    });
    // 在途期间锁定作物选择，避免「按柑橘提交、按水稻渲染」的错位
    document.querySelectorAll('.crop-btn').forEach(btn => { btn.disabled = busy; });
    const startBtn = document.getElementById('start-diagnosis');
    if (startBtn) {
        startBtn.innerHTML = busy
            ? '<i class="fas fa-spinner fa-spin"></i> 正在分析...'
            : '<i class="fas fa-search"></i> 开始诊断';
    }
}

function initPestDiagnosis() {
    if (!PestState.initialized) {
        PestState.initialized = true;

        // 作物选择（仅首次绑定一次事件，避免重复 addEventListener 造成重复触发）
        document.querySelectorAll('.crop-btn').forEach(btn => {
            btn.addEventListener('click', function() {
                document.querySelectorAll('.crop-btn').forEach(b => b.classList.remove('active'));
                this.classList.add('active');
                PestState.selectedCrop = this.dataset.crop;
                PestState.userSelectedCrop = true;
                updateDiagSymptomPlaceholder();
            });
        });

        // 开始诊断
        document.getElementById('start-diagnosis')?.addEventListener('click', runDiagnosis);

        // 上传照片：文件先在本机压缩，再作为 base64 随诊断请求一起提交。
        // 此前这里只调 runDiagnosis()、从不读取文件，等于把用户的照片直接丢掉。
        document.getElementById('upload-photo-btn')?.addEventListener('click', () => {
            document.getElementById('plant-image')?.click();
        });
        document.getElementById('plant-image')?.addEventListener('change', function() {
            const files = Array.prototype.slice.call(this.files || []);
            this.value = '';   // 复位，保证再次选择同一张照片也能触发 change
            handleDiagFiles(files);
        });

        // 症状字数计数
        document.getElementById('symptom-text')?.addEventListener('input', function() {
            const counter = document.getElementById('symptom-count');
            if (counter) counter.textContent = String(this.value.length);
        });

        // 重新诊断
        document.getElementById('re-diagnose')?.addEventListener('click', () => {
            document.getElementById('diagnosis-result')?.classList.add('is-hidden');
            const box = document.getElementById('symptom-text');
            if (box) { box.value = ''; box.focus(); }
            const counter = document.getElementById('symptom-count');
            if (counter) counter.textContent = '0';
            PestState.images = [];
            renderDiagPhotos();
        });

        // 复制结果
        document.getElementById('copy-diagnosis')?.addEventListener('click', () => {
            const result = document.getElementById('diagnosis-result');
            if (result) {
                const text = result.innerText;
                copyText(text, '诊断结果已复制');
            }
        });
    }

    // 每次打开面板都同步一次默认作物。
    // 此前该同步被 initialized 门禁包裹，只在首次初始化时执行一次，
    // 导致「先选水稻（诊断面板未打开）→ 再打开诊断」仍停留在荔枝。
    syncPestCropFromProduct();
    updateDiagSymptomPlaceholder();
}

// 把农时日历当前选中的作物同步为诊断面板的默认作物。
// 单向同步：只影响诊断面板，不反向影响日历。诊断库未覆盖的作物保持原选择。
// 用户在面板里手动选过作物之后不再覆盖 —— 否则「收起面板再展开」会把选择静默改回去。
function syncPestCropFromProduct() {
    if (PestState.userSelectedCrop) return;
    const current = AppState.currentProduct;
    if (!current || PestState.selectedCrop === current) return;
    const match = document.querySelector(`.crop-btn[data-crop="${current}"]`);
    if (!match) return;
    document.querySelectorAll('.crop-btn').forEach(b => b.classList.remove('active'));
    match.classList.add('active');
    PestState.selectedCrop = current;
}

// A1：顶部作物切换时调用 —— 复位「用户手选过」门禁后再同步一次。
// 两条路径的区别就是本项目此前漏掉的那一条：
//   · 顶部作物变化  -> 学生的主语境真的换了，面板必须跟随（本函数）
//   · 仅收起/再展开 -> 门禁仍生效，不静默改掉面板内的手选（syncPestCropFromProduct 内部）
function resetPestCropToCurrent() {
    PestState.userSelectedCrop = false;
    syncPestCropFromProduct();
}

// ---------- 照片读取 / 压缩 / 预览 ----------

function readFileAsDataUrl(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = () => reject(new Error('read_failed'));
        reader.readAsDataURL(file);
    });
}

// 用 canvas 把照片压到长边 <= maxEdge、JPEG 质量 quality。
// 返回 null 表示浏览器无法解码这张照片（例如部分 HEIC 格式）。
function compressImage(dataUrl, maxEdge, quality) {
    return new Promise((resolve) => {
        const img = new Image();
        img.onload = () => {
            try {
                const scale = Math.min(1, maxEdge / Math.max(img.width, img.height));
                const width = Math.max(1, Math.round(img.width * scale));
                const height = Math.max(1, Math.round(img.height * scale));
                const canvas = document.createElement('canvas');
                canvas.width = width;
                canvas.height = height;
                canvas.getContext('2d').drawImage(img, 0, 0, width, height);
                resolve(canvas.toDataURL('image/jpeg', quality));
            } catch (e) {
                resolve(null);
            }
        };
        img.onerror = () => resolve(null);
        img.src = dataUrl;
    });
}

function dataUrlByteLength(dataUrl) {
    const text = String(dataUrl || '');
    const idx = text.indexOf(',');
    const b64 = idx >= 0 ? text.slice(idx + 1) : text;
    return Math.floor(b64.length * 3 / 4);
}

async function handleDiagFiles(files) {
    const list = Array.prototype.slice.call(files || []);
    if (!list.length) return;

    const room = DIAG_MAX_IMAGES - PestState.images.length;
    if (room <= 0) {
        showNotification(`最多上传 ${DIAG_MAX_IMAGES} 张照片`, 'warning');
        return;
    }
    if (list.length > room) {
        showNotification(`最多上传 ${DIAG_MAX_IMAGES} 张照片，已保留前 ${room} 张`, 'warning');
    }

    for (const file of list.slice(0, room)) {
        let raw = null;
        try {
            raw = await readFileAsDataUrl(file);
        } catch (e) {
            raw = null;
        }
        if (!raw) { showNotification('读取照片失败，请重新选择', 'warning'); continue; }

        const compressed = await compressImage(raw, DIAG_IMAGE_MAX_EDGE, DIAG_IMAGE_QUALITY);
        if (!compressed) {
            showNotification('无法识别这张照片的格式，请改用 JPG / PNG', 'warning');
            continue;
        }
        if (dataUrlByteLength(compressed) > DIAG_MAX_IMAGE_BYTES) {
            showNotification('照片过大，请换一张更小的图片', 'warning');
            continue;
        }
        PestState.images.push(compressed);
    }
    renderDiagPhotos();
}

function renderDiagPhotos() {
    const box = document.getElementById('diag-photo-preview');
    if (!box) return;
    box.innerHTML = '';
    if (!PestState.images.length) {
        box.classList.add('is-hidden');
        return;
    }

    const tip = document.createElement('span');
    tip.className = 'diag-photo-tip';
    tip.textContent = `已选择 ${PestState.images.length} 张照片，将随诊断一并提交`;
    box.appendChild(tip);

    PestState.images.forEach((src, idx) => {
        const item = document.createElement('div');
        item.className = 'diag-photo-item';
        const img = document.createElement('img');
        img.src = src;
        img.alt = `待诊断照片 ${idx + 1}`;
        item.appendChild(img);

        const del = document.createElement('button');
        del.type = 'button';
        del.className = 'diag-photo-remove';
        del.setAttribute('aria-label', '移除这张照片');
        del.innerHTML = '<i class="fas fa-times"></i>';
        del.addEventListener('click', () => {
            PestState.images.splice(idx, 1);
            renderDiagPhotos();
        });
        item.appendChild(del);
        box.appendChild(item);
    });

    const clear = document.createElement('button');
    clear.type = 'button';
    clear.className = 'btn btn-outline btn-sm';
    clear.textContent = '清空照片';
    clear.addEventListener('click', () => {
        PestState.images = [];
        renderDiagPhotos();
    });
    box.appendChild(clear);
    box.classList.remove('is-hidden');
}

// ---------- 请求与错误处理 ----------

// 失败类型按服务端下发的 code 判定，不用中文文案正则
const DIAG_ERROR_TEXT = {
    bad_request: '请求格式不正确，请刷新页面后重试。',
    unknown_crop: '暂不支持该作物，请重新选择。',
    symptoms_too_long: `症状描述请控制在 ${DIAG_SYMPTOMS_MAXLEN} 字以内。`,
    empty_symptoms: '请先上传一张作物照片，或描述症状后再开始诊断。',
    bad_image: '照片格式不受支持，请上传 JPG / PNG / WebP 格式的照片。',
    image_too_large: '照片过大，请换一张更小的图片。',
    too_many_images: `一次最多上传 ${DIAG_MAX_IMAGES} 张照片。`,
    rate_limited: '诊断请求过于频繁，请稍后再试。',
    ai_not_configured: 'AI 服务尚未启用，暂时无法进行图片诊断。你可以改用文字描述症状。',
    ai_vision_unavailable: '图片诊断功能暂未开放，你可以改用文字描述症状。',
    ai_unavailable: 'AI 服务暂时不可用，请稍后重试；如需即时帮助可拨打 12316 三农服务热线。',
    no_match: '未能从描述中匹配到对应的病害，请补充发病部位、病斑颜色与形状等更具体的症状后重试。'
};

function diagErrorText(status, data) {
    const code = data && data.code;
    if (code && DIAG_ERROR_TEXT[code]) return DIAG_ERROR_TEXT[code];
    if (data && data.message) return String(data.message);
    if (status === 413) return '照片过大，请换一张更小的图片。';
    return '诊断服务暂时不可用，请稍后重试。';
}

// 诊断接口不走 apiCall：需要在非 2xx 时也能读到响应体里的 code。
async function postDiagnosis(payload) {
    const options = {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    };
    if (AppState.sessionId) options.headers['X-Session-Id'] = AppState.sessionId;
    const resp = await fetch(`${API_BASE_URL}/api/agriculture/diagnose`, options);
    let data = null;
    try { data = await resp.json(); } catch (e) { data = null; }
    return { ok: resp.ok, status: resp.status, data: data };
}

function clearDiagError() {
    const el = document.getElementById('diagnosis-error');
    if (el) { el.textContent = ''; el.classList.add('is-hidden'); }
}

// 病名/置信度区、三栏明细区、额外信息区：失败时整体收起，
// 否则会留下一排空卡片，看起来像渲染坏了。
const DIAG_SECTION_CLASSES = ['result-info', 'diagnosis-grid', 'diagnosis-extra'];

function setDiagSectionsVisible(visible) {
    DIAG_SECTION_CLASSES.forEach(cls => {
        const el = document.querySelector('#diagnosis-result .' + cls);
        if (el) el.classList.toggle('is-hidden', !visible);
    });
}

// 失败时清空上一次的结论：否则旧病名与旧来源角标会继续留在页面上，
// 被用户误认为本次诊断的结果。
function renderDiagError(message) {
    clearDiagError();
    const errEl = document.getElementById('diagnosis-error');
    if (errEl) {
        errEl.textContent = message;
        errEl.classList.remove('is-hidden');
    }

    const nameEl = document.getElementById('disease-name');
    if (nameEl) nameEl.textContent = '';
    ['symptoms-list', 'treatment-list', 'prevention-list'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.innerHTML = '';
    });
    ['timing-text', 'note-text'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.textContent = '';
    });
    document.getElementById('diagnosis-source')?.classList.add('is-hidden');
    document.getElementById('severity-badge')?.classList.add('is-hidden');
    const symTitle = document.getElementById('symptoms-title');
    if (symTitle) symTitle.textContent = '症状表现';
    const titleEl = document.getElementById('diagnosis-title');
    if (titleEl) titleEl.textContent = '诊断未完成';
    setDiagSectionsVisible(false);

    document.getElementById('diagnosis-result')?.classList.remove('is-hidden');
}

async function runDiagnosis() {
    if (PestState.busy) return;

    const symptoms = (document.getElementById('symptom-text')?.value || '').trim();
    const images = PestState.images.slice();

    if (!symptoms && !images.length) {
        showNotification('请先上传一张作物照片，或描述症状', 'warning');
        document.getElementById('symptom-text')?.focus();
        return;
    }

    setDiagBusy(true);
    showLoading('正在分析，请稍候...');
    try {
        const payload = { crop: PestState.selectedCrop, symptoms: symptoms };
        if (images.length) payload.image = images;

        const res = await postDiagnosis(payload);
        const data = res.data || {};
        if (res.ok && data.success && data.diagnosis) {
            renderDiagnosis(data.diagnosis);
        } else {
            renderDiagError(diagErrorText(res.status, data));
        }
    } catch (e) {
        renderDiagError('诊断服务暂时不可用，请稍后重试。');
    } finally {
        hideLoading();
        setDiagBusy(false);
    }
}

// 诊断字段归一化：知识库给的是数组，但模型偶尔会把多条目写成一段字符串，
// 此处统一成字符串数组，避免 .map is not a function 导致整个结果区渲染中断。
function diagnosisList(value) {
    if (Array.isArray(value)) {
        return value.map(v => String(v == null ? '' : v).trim()).filter(Boolean);
    }
    if (value == null || value === '') return [];
    return [String(value).trim()].filter(Boolean);
}

// 严重程度归一化：模型可能返回「中度偏重」「轻微」这类值，
// 归到三档配色；无法归类的原样展示且不套用配色。
function normalizeSeverity(value) {
    const text = String(value == null ? '' : value).trim();
    if (!text) return { text: '', level: '' };
    if (text.indexOf('重') >= 0) return { text: text, level: '重度' };
    if (text.indexOf('轻') >= 0 || text.indexOf('微') >= 0) return { text: text, level: '轻度' };
    if (text.indexOf('中') >= 0) return { text: text, level: '中度' };
    return { text: text, level: '' };
}

// 置信度已整块下线（见 renderDiagnosis 注释），原先的 confidencePercent() 归一化函数
// 随之删除 —— 留一个没有任何调用者的函数，只会让人以为界面上还有这个数值。

function renderDiagnosis(d) {
    clearDiagError();
    setDiagSectionsVisible(true);
    const fromKb = d.source === 'knowledge_base';

    // 病名
    const nameEl = document.getElementById('disease-name');
    if (nameEl) nameEl.textContent = (d.crop_icon || '') + ' ' + (d.disease || '待确认');

    // 来源标注：区分 AI 结论与知识库降级结果，并把免责说明常驻展示
    const titleEl = document.getElementById('diagnosis-title');
    if (titleEl) titleEl.textContent = fromKb ? '知识库匹配结果' : '诊断结果';
    const srcEl = document.getElementById('diagnosis-source');
    if (srcEl) {
        const label = d.source_label || (fromKb ? '本地知识库匹配' : 'AI 模型生成');
        const note = d.source_note || '仅供参考，请以当地农技站指导为准。';
        srcEl.textContent = '结论来源：' + label + ' · ' + note;
        srcEl.dataset.source = fromKb ? 'knowledge_base' : 'ai';
        srcEl.classList.remove('is-hidden');
    }

    // 严重程度
    const sevBadge = document.getElementById('severity-badge');
    if (sevBadge) {
        const sev = normalizeSeverity(d.severity);
        sevBadge.textContent = sev.text;
        sevBadge.dataset.level = sev.level;
        sevBadge.classList.toggle('is-hidden', !sev.text);
    }

    // 置信度：整块下线，不再渲染。
    // 原因有两层，任何一层单独成立都足够：
    //   ① 知识库条目的 confidence 是 PEST_KNOWLEDGE 里的固定常量，不是真实匹配度；
    //   ② AI 自评的百分比同样不可信 —— 同一个症状模型曾给出 0.95 却配了错误的病名。
    // 界面只保留结论与来源标注，不给一个「看着像算过、其实没算过」的数字。
    // 服务端也已从提示词契约里删掉 confidence，并在 _parse_ai_diagnosis 里兜底剔除。

    // 症状区标题：知识库列出的是「该病害的典型症状」，不是用户描述的内容，
    // 标题必须说清楚，否则匹配错误时会用一串陌生症状反向强化错误结论。
    const symTitle = document.getElementById('symptoms-title');
    if (symTitle) symTitle.textContent = fromKb ? '该病典型症状' : '症状表现';

    // 症状 / 防治方案 / 预防措施
    // 三处均为模型或知识库产出，一律先转义再拼接，避免 innerHTML 注入
    const LIST_TARGETS = [
        ['symptoms-list', d.symptoms],
        ['treatment-list', d.treatment],
        ['prevention-list', d.prevention]
    ];
    LIST_TARGETS.forEach(([id, value]) => {
        const el = document.getElementById(id);
        if (!el) return;
        el.innerHTML = diagnosisList(value).map(item => `<li>${escapeHtml(item)}</li>`).join('');
    });

    // 额外信息
    const timingText = document.getElementById('timing-text');
    if (timingText) timingText.textContent = d.timing || '发病初期';

    const noteText = document.getElementById('note-text');
    if (noteText) noteText.textContent = d.note || '';

    // 显示结果
    document.getElementById('diagnosis-result')?.classList.remove('is-hidden');
}

// ==================== 常见病虫害速查 ====================
//
// 数据来自只读接口 /api/agriculture/pest-knowledge：一次取回、本地筛选。
// 与后台一致的三条硬约定：
//   1. 来源资料没给出的数值就是「未提供」，界面绝不替用户推断（安全间隔期尤其如此）；
//   2. 没有授权实拍图时显示「暂无实拍图」占位，绝不用示意图或生成图冒充真实病征；
//   3. 加载失败必须是可见的错误态 + 重试，不能用空列表冒充「没有数据」。

const PestGuideState = {
    loaded: false,
    loading: false,
    entries: [],
    crops: [],
    disclaimer: '',
    crop: '',                 // '' 表示全部作物
    // A4：速查的作物筛选默认跟随顶部「当前作物」，理由与诊断面板一致 ——
    // 同一个页面里「当前作物」只应有一套含义。用户在这里手选过筛选之后不再被覆盖。
    userSelectedCrop: false,
    keyword: '',
    bound: false,
    lastFocus: null,          // 打开详情前的焦点元素，关闭后还回去
    prevBodyOverflow: null
};

// escapeHtml（textContent → innerHTML）不处理引号，直接拼进 src="" / title="" 并不安全；
// 属性上下文单独用这一套。
function pestAttr(value) {
    return String(value == null ? '' : value)
        .replace(/&/g, '&amp;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}

// 只让 http/https 进 href。属性转义挡不住 javascript: / data: 这类伪协议，
// 而 image.source_url 与 sources[].url 都会拼进 <a href>，所以必须再做一次协议白名单。
function pestSafeUrl(value) {
    const u = String(value == null ? '' : value).trim();
    return /^https?:\/\//i.test(u) ? u : '';
}

function pestArray(value) {
    return Array.isArray(value) ? value : [];
}

function pestHas(value) {
    return value !== null && value !== undefined && String(value).trim() !== '';
}

function pestCropName(cropId) {
    if (!cropId) return '全部作物';
    const hit = PestGuideState.crops.filter(function(c) { return c.id === cropId; })[0];
    return (hit && hit.name) ? hit.name : cropId;
}

// ---------- 入口与懒加载 ----------

function setupPestGuide() {
    const section = document.getElementById('pest-guide');
    if (!section) return;
    bindPestGuideOnce();

    // 首屏就落在农业技能板块 → 立即取；否则等它真正进入视口再取，不与首屏资源抢带宽。
    if (section.getClientRects().length > 0) {
        loadPestKnowledge();
        return;
    }
    if ('IntersectionObserver' in window) {
        const io = new IntersectionObserver(function(entries) {
            for (let i = 0; i < entries.length; i++) {
                if (entries[i].isIntersecting) {
                    io.disconnect();
                    loadPestKnowledge();
                    return;
                }
            }
        }, { rootMargin: '120px' });
        io.observe(section);
    } else {
        loadPestKnowledge();
    }
}

function bindPestGuideOnce() {
    if (PestGuideState.bound) return;
    PestGuideState.bound = true;

    // 作物筛选：事件委托，筛选栏整体重绘后不需要重新绑定
    const filter = document.getElementById('pest-crop-filter');
    if (filter) {
        filter.addEventListener('click', function(e) {
            const btn = e.target.closest ? e.target.closest('.pest-crop-btn') : null;
            if (!btn || !filter.contains(btn)) return;
            const next = btn.getAttribute('data-pest-crop') || '';
            if (next === PestGuideState.crop) return;
            PestGuideState.crop = next;
            // A4：手选即上锁，此后顶部作物变化不再改这里的筛选（与诊断面板同语义）
            PestGuideState.userSelectedCrop = true;
            renderPestCropFilter();
            renderPestCards();
        });
    }

    // 搜索：本地过滤，不上行，无需防抖
    const search = document.getElementById('pest-guide-search');
    if (search) {
        search.addEventListener('input', function() {
            PestGuideState.keyword = this.value || '';
            renderPestCards();
        });
    }

    // 卡片打开详情（点击 + 键盘）
    const grid = document.getElementById('pest-guide-grid');
    if (grid) {
        grid.addEventListener('click', function(e) {
            const card = e.target.closest ? e.target.closest('.pest-card') : null;
            if (card) openPestModal(card.getAttribute('data-pest-id'));
        });
        grid.addEventListener('keydown', function(e) {
            if (e.key !== 'Enter' && e.key !== ' ') return;
            const card = e.target.closest ? e.target.closest('.pest-card') : null;
            if (!card) return;
            e.preventDefault();
            openPestModal(card.getAttribute('data-pest-id'));
        });
    }

    // 关闭：右上角按钮 + 遮罩 + ESC
    document.getElementById('pest-modal-close')?.addEventListener('click', closePestModal);
    const modal = document.getElementById('pest-modal');
    if (modal) {
        modal.addEventListener('click', function(e) {
            if (e.target.closest && e.target.closest('[data-pest-close]')) closePestModal();
        });
    }
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && isPestModalOpen()) closePestModal();
    });

    // 兜底触发：用户点进「农业技能」就直接取数，不必等滚动到速查区块。
    // IntersectionObserver 对「display:none 转可见」的响应并不总可靠，
    // 而这块数据取早了也只是提前 1 个请求，取晚了就是一片空白骨架屏。
    document.addEventListener('click', function(e) {
        const nav = e.target.closest ? e.target.closest('.nav-item') : null;
        if (nav && nav.getAttribute('data-tab') === 'agriculture') loadPestKnowledge();
    }, true);
}

function isPestModalOpen() {
    const modal = document.getElementById('pest-modal');
    return !!modal && !modal.classList.contains('is-hidden');
}

// ---------- 取数与状态渲染 ----------

function loadPestKnowledge(force) {
    if (PestGuideState.loading) return Promise.resolve();
    if (PestGuideState.loaded && !force) return Promise.resolve();

    const grid = document.getElementById('pest-guide-grid');
    const emptyEl = document.getElementById('pest-guide-empty');
    const metaEl = document.getElementById('pest-guide-meta');

    PestGuideState.loading = true;
    if (emptyEl) emptyEl.classList.add('is-hidden');
    if (metaEl) metaEl.textContent = '';
    // 骨架屏复用 core.js 的通用实现，不另造一套加载样式
    if (grid) showSkeleton(grid, 'card', 6);

    return apiCall('/api/agriculture/pest-knowledge').then(function(data) {
        if (!data || data.success !== true) {
            throw new Error((data && data.message) || '数据格式异常');
        }
        PestGuideState.entries = pestArray(data.entries);
        PestGuideState.crops = pestArray(data.crops);
        PestGuideState.disclaimer = data.disclaimer || '';
        PestGuideState.loaded = true;
        // A4：首次拿到数据时按顶部「当前作物」预筛一次（用户此前手选过则不覆盖）
        applyPestGuideCrop(false);
        renderPestDisclaimer();
        renderPestCropFilter();
        renderPestCards();
    }).catch(function(err) {
        // 失败时不能留下空网格，否则会被当成「一条都没有」
        renderPestGuideError(err);
    }).then(function() {
        PestGuideState.loading = false;
    });
}

function renderPestGuideError(err) {
    const grid = document.getElementById('pest-guide-grid');
    const emptyEl = document.getElementById('pest-guide-empty');
    const metaEl = document.getElementById('pest-guide-meta');
    if (emptyEl) emptyEl.classList.add('is-hidden');
    if (metaEl) metaEl.textContent = '';
    if (!grid) return;
    const detail = (err && err.message) ? err.message : '网络异常';
    showErrorState(grid, '速查数据加载失败（' + detail + '）', function() {
        loadPestKnowledge(true);
    });
}

function renderPestDisclaimer() {
    const el = document.getElementById('pest-guide-disclaimer');
    if (el) el.textContent = PestGuideState.disclaimer || '';
}

// ---------- 作物筛选 ----------

// A4：把速查筛选对齐到顶部「当前作物」。返回是否真的改了筛选值。
// 两条门禁，与诊断面板（syncPestCropFromProduct / resetPestCropToCurrent）完全一致：
//   · force=true  —— 顶部作物变化时调用，复位「手选过」的门禁再跟随；
//   · force=false —— 首次加载时调用，只在用户没手选过时跟随。
// 另一个必须的判断：速查数据里没有这个作物时不切，否则会筛出「0 条」，看起来像功能坏了。
function applyPestGuideCrop(force) {
    if (!force && PestGuideState.userSelectedCrop) return false;
    const current = AppState.currentProduct;
    if (!current || PestGuideState.crop === current) return false;
    const known = (PestGuideState.crops || []).some(function(c) { return c.id === current; });
    if (!known) return false;
    PestGuideState.crop = current;
    return true;
}

function resetPestGuideCropToCurrent() {
    PestGuideState.userSelectedCrop = false;
    if (PestGuideState.loaded && applyPestGuideCrop(true)) {
        renderPestCropFilter();
        renderPestCards();
    }
}

function renderPestCropFilter() {
    const wrap = document.getElementById('pest-crop-filter');
    if (!wrap) return;

    const counts = {};
    PestGuideState.entries.forEach(function(entry) {
        const key = entry.crop || '';
        counts[key] = (counts[key] || 0) + 1;
    });

    let html = pestCropBtnHTML('', '全部作物', '📚', PestGuideState.entries.length);
    PestGuideState.crops.forEach(function(crop) {
        html += pestCropBtnHTML(crop.id, crop.name, crop.icon, counts[crop.id] || 0);
    });
    wrap.innerHTML = html;
}

function pestCropBtnHTML(id, name, icon, count) {
    const active = PestGuideState.crop === id;
    return '<button type="button" class="pest-crop-btn' + (active ? ' active' : '') + '"' +
        ' role="tab" aria-selected="' + (active ? 'true' : 'false') + '"' +
        ' data-pest-crop="' + pestAttr(id) + '">' +
        '<span aria-hidden="true">' + escapeHtml(icon || '') + '</span> ' +
        escapeHtml(name || '') +
        '<span class="pest-crop-count">' + count + '</span>' +
        '</button>';
}

// ---------- 卡片列表 ----------

function pestGuideMatches() {
    const kw = String(PestGuideState.keyword || '').trim().toLowerCase();
    return PestGuideState.entries.filter(function(entry) {
        if (PestGuideState.crop && entry.crop !== PestGuideState.crop) return false;
        if (!kw) return true;
        const blob = [
            entry.disease, entry.alias, entry.pathogen, entry.crop_name,
            pestArray(entry.symptoms).join(' ')
        ].join(' ').toLowerCase();
        return blob.indexOf(kw) !== -1;
    });
}

function pestGuideMetaText(shown) {
    if (!PestGuideState.loaded) return '';
    const total = PestGuideState.entries.length;
    const kw = String(PestGuideState.keyword || '').trim();
    const scope = pestCropName(PestGuideState.crop);
    if (kw) return '「' + kw + '」匹配 ' + shown + ' 条 · ' + scope + ' · 速查共 ' + total + ' 条';
    return scope + '：' + shown + ' 条 · 速查共 ' + total + ' 条';
}

function renderPestCards() {
    const grid = document.getElementById('pest-guide-grid');
    const emptyEl = document.getElementById('pest-guide-empty');
    const metaEl = document.getElementById('pest-guide-meta');
    if (!grid) return;

    const list = pestGuideMatches();
    grid.innerHTML = list.map(pestCardHTML).join('');
    if (metaEl) metaEl.textContent = pestGuideMetaText(list.length);

    // 只有「确实取到数据、但筛完为空」才提示无匹配；
    // 数据还没取到时不能显示「没有匹配的条目」。
    if (emptyEl) {
        emptyEl.classList.toggle('is-hidden', !(PestGuideState.loaded && list.length === 0));
    }
}

function pestCardHTML(entry) {
    const isPest = entry.kind === 'pest';
    const kindTag = '<span class="pest-kind-tag ' + (isPest ? 'is-pest' : 'is-disease') + '">' +
        (isPest ? '虫害' : '病害') + '</span>';
    const cropTag = pestHas(entry.crop_name)
        ? '<span class="pest-kind-tag">' + escapeHtml(entry.crop_name) + '</span>'
        : '';

    const thumb = (entry.image && entry.image.file)
        ? '<img src="' + pestAttr(entry.image.file) + '" alt="' + pestAttr(entry.disease + ' 实拍图') +
          '" loading="lazy">'
        : '<div class="pest-card-thumb-empty"><i class="fas fa-image" aria-hidden="true"></i>' +
          '<span>暂无实拍图</span></div>';

    const alias = pestHas(entry.alias)
        ? '<p class="pest-card-alias">别名：' + escapeHtml(entry.alias) + '</p>'
        : '';

    const part = pestHas(entry.part)
        ? '<span class="pest-card-part" title="' + pestAttr(entry.part) + '">' +
          '<i class="fas fa-crosshairs" aria-hidden="true"></i> ' + escapeHtml(entry.part) + '</span>'
        : '<span class="pest-card-part"></span>';

    return '<article class="pest-card" role="button" tabindex="0" data-pest-id="' +
        pestAttr(entry.id) + '" aria-label="查看' + pestAttr(entry.disease) + '详情">' +
        '<div class="pest-card-thumb">' +
            '<div class="pest-card-tags">' + kindTag + cropTag + '</div>' +
            thumb +
        '</div>' +
        '<div class="pest-card-body">' +
            '<h4>' + escapeHtml(entry.disease) + '</h4>' + alias +
            '<div class="pest-card-foot">' + part +
                '<span class="pest-card-part">详情 ›</span>' +
            '</div>' +
        '</div>' +
    '</article>';
}

// ---------- 详情弹窗 ----------

function openPestModal(id) {
    const entry = PestGuideState.entries.filter(function(e) { return e.id === id; })[0];
    if (!entry) return;

    const modal = document.getElementById('pest-modal');
    const titleEl = document.getElementById('pest-modal-title');
    const bodyEl = document.getElementById('pest-modal-body');
    if (!modal || !bodyEl) return;

    if (titleEl) {
        const sub = [];
        if (pestHas(entry.crop_name)) sub.push(entry.crop_name);
        sub.push(entry.kind === 'pest' ? '虫害' : '病害');
        titleEl.innerHTML = escapeHtml(entry.disease) +
            '<span class="pest-modal-sub">' + escapeHtml(sub.join(' · ')) + '</span>';
    }
    bodyEl.innerHTML = pestModalHTML(entry);

    PestGuideState.lastFocus = document.activeElement;
    modal.classList.remove('is-hidden');
    // 锁背景滚动；记下原值，关闭时原样恢复，避免影响其它弹窗
    if (PestGuideState.prevBodyOverflow === null) {
        PestGuideState.prevBodyOverflow = document.body.style.overflow || '';
    }
    document.body.style.overflow = 'hidden';
    bodyEl.scrollTop = 0;
    document.getElementById('pest-modal-close')?.focus();
}

function closePestModal() {
    const modal = document.getElementById('pest-modal');
    if (!modal || modal.classList.contains('is-hidden')) return;

    modal.classList.add('is-hidden');
    if (PestGuideState.prevBodyOverflow !== null) {
        document.body.style.overflow = PestGuideState.prevBodyOverflow;
        PestGuideState.prevBodyOverflow = null;
    }
    const bodyEl = document.getElementById('pest-modal-body');
    if (bodyEl) bodyEl.innerHTML = '';

    const back = PestGuideState.lastFocus;
    PestGuideState.lastFocus = null;
    if (back && typeof back.focus === 'function' && document.contains(back)) back.focus();
}

function pestModalHTML(entry) {
    const blocks = [];
    const symptoms = pestArray(entry.symptoms);
    const treatment = pestArray(entry.treatment);
    const prevention = pestArray(entry.prevention);
    const registered = pestArray(entry.registered);
    const chemTable = pestArray(entry.chem_table);

    // 实拍图 / 明确占位 —— 没有授权图就不放图，绝不用示意图冒充
    if (entry.image && entry.image.file) {
        const credit = pestHas(entry.image.credit) ? escapeHtml(entry.image.credit) : '';
        const license = pestHas(entry.image.license) ? escapeHtml(entry.image.license) : '';
        const shot = pestHas(entry.image.shot_date) ? '摄于 ' + escapeHtml(entry.image.shot_date) : '';
        const srcUrl = pestSafeUrl(entry.image.source_url);
        const link = srcUrl
            ? '<a href="' + pestAttr(srcUrl) + '" target="_blank" rel="noopener noreferrer">查看图片来源</a>'
            : '';
        // 署名 / 许可 / 拍摄日期 / 来源，缺哪个就不占位（CC 类许可要求标注许可类型）
        const caption = [credit, license, shot, link]
            .filter(function (s) { return !!s; }).join(' · ');
        // 图注：单独一行，说明这张照片拍的是哪个**虫态**（若虫/成虫）、哪个**具体种**。
        // 稻飞虱 / 水稻螟虫 / 荔枝卷叶虫 / 龙眼蚧壳虫 / 蔬菜蚜虫 这些条目名是类群名，
        // 照片必然只拍到其中一个种；不标出来就等于把「一种」冒充「一类」。
        const captionNote = pestHas(entry.image.caption)
            ? '<span class="pest-modal-caption-note">' + escapeHtml(entry.image.caption) + '</span>'
            : '';
        blocks.push(
            '<figure class="pest-modal-figure">' +
                '<img src="' + pestAttr(entry.image.file) + '" alt="' + pestAttr(entry.disease + ' 实拍图') + '">' +
                '<figcaption>' + captionNote + caption + '</figcaption>' +
            '</figure>'
        );
    } else {
        blocks.push(
            '<p class="pest-modal-noimg">' +
                '<i class="fas fa-image" aria-hidden="true"></i> ' +
                '该条目暂无可用授权实拍图，此处不提供示意图。请对照下方症状文字与当地农技员核实。' +
            '</p>'
        );
    }

    // 基本事实
    const facts = ['<span class="pest-fact"><b>类别：</b>' +
        (entry.kind === 'pest' ? '虫害' : '病害') + '</span>'];
    if (pestHas(entry.alias)) facts.push('<span class="pest-fact"><b>别名：</b>' + escapeHtml(entry.alias) + '</span>');
    if (pestHas(entry.pathogen)) facts.push('<span class="pest-fact"><b>病原/学名：</b>' + escapeHtml(entry.pathogen) + '</span>');
    if (pestHas(entry.part)) facts.push('<span class="pest-fact"><b>主要为害部位：</b>' + escapeHtml(entry.part) + '</span>');
    if (pestHas(entry.severity)) facts.push('<span class="pest-fact"><b>危害程度：</b>' + escapeHtml(entry.severity) + '</span>');
    blocks.push('<div class="pest-facts">' + facts.join('') + '</div>');

    if (symptoms.length) blocks.push(pestBlockHTML('典型症状', 'fas fa-stethoscope', pestListHTML(symptoms)));
    if (pestHas(entry.occurrence)) {
        blocks.push(pestBlockHTML('发生规律', 'fas fa-cloud-rain',
            '<p class="pest-paragraph">' + escapeHtml(entry.occurrence) + '</p>'));
    }
    if (treatment.length) blocks.push(pestBlockHTML('化学防治要点', 'fas fa-spray-can', pestListHTML(treatment)));
    if (prevention.length) blocks.push(pestBlockHTML('农业防治与预防', 'fas fa-shield', pestListHTML(prevention)));
    if (registered.length) blocks.push(pestBlockHTML('推荐 / 登记药剂', 'fas fa-flask', pestTagsHTML(registered)));
    if (chemTable.length) blocks.push(pestBlockHTML('用药参考表', 'fas fa-table', pestChemTableHTML(chemTable)));
    if (pestHas(entry.safety_note)) {
        blocks.push('<p class="pest-warn"><i class="fas fa-exclamation-triangle" aria-hidden="true"></i>' +
            '<span>' + escapeHtml(entry.safety_note) + '</span></p>');
    }

    blocks.push(pestSourcesHTML(entry));
    return blocks.join('');
}

function pestBlockHTML(title, iconClass, inner) {
    return '<section>' +
        '<h4 class="pest-block-title"><i class="' + pestAttr(iconClass) + '" aria-hidden="true"></i>' +
        escapeHtml(title) + '</h4>' + inner + '</section>';
}

function pestListHTML(items) {
    return '<ul class="pest-list">' + items.map(function(item) {
        return '<li>' + escapeHtml(item) + '</li>';
    }).join('') + '</ul>';
}

function pestTagsHTML(items) {
    return '<div class="pest-tags">' + items.map(function(item) {
        return '<span class="pest-tag">' + escapeHtml(item) + '</span>';
    }).join('') + '</div>';
}

function pestChemCell(value, unit) {
    if (!pestHas(value)) return '<td class="is-empty">未提供</td>';
    return '<td>' + escapeHtml(String(value)) + (unit ? ' ' + unit : '') + '</td>';
}

function pestChemTableHTML(rows) {
    const head = '<thead><tr><th>药剂</th><th>参考用量</th><th>安全间隔期</th>' +
        '<th>每季最多使用</th></tr></thead>';
    const body = rows.map(function(row) {
        return '<tr>' +
            '<td>' + escapeHtml(row.agent || '') + '</td>' +
            pestChemCell(row.dose, '') +
            pestChemCell(row.interval_days, '天') +
            pestChemCell(row.max_times, '次') +
        '</tr>';
    }).join('');
    return '<div class="pest-table-wrap"><table class="pest-table">' + head +
        '<tbody>' + body + '</tbody></table></div>' +
        '<p class="pest-refnote">表中「未提供」表示所引来源未标注该项数值，本速查不作推算，' +
        '实际以所购农药标签为准。</p>';
}

function pestSourcesHTML(entry) {
    const sources = pestArray(entry.sources);
    let inner;
    if (!sources.length) {
        inner = '<p class="pest-refnote">该条目未登记具体出处，请谨慎参考。</p>';
    } else {
        inner = '<div class="pest-sources">' + sources.map(function(src) {
            const docBits = [];
            // 「待核」是明确的状态（照实说没核到）；「—」/空 表示这类来源本来就没有文号，直接不显示
            const docNo = String(src.doc_no == null ? '' : src.doc_no).trim();
            if (docNo === '待核') docBits.push('文号待核');
            else if (docNo && docNo !== '—' && docNo !== '-') docBits.push(escapeHtml(docNo));
            if (pestHas(src.date)) docBits.push(escapeHtml(src.date));
            const docLine = docBits.length
                ? ' <span class="pest-source-doc">（' + docBits.join(' · ') + '）</span>' : '';
            const srcUrl = pestSafeUrl(src.url);
            const link = srcUrl
                ? '<br><a href="' + pestAttr(srcUrl) + '" target="_blank" rel="noopener noreferrer">' +
                  escapeHtml(srcUrl) + '</a>'
                : '';
            return '<div class="pest-source-item">' +
                '<strong>' + escapeHtml(src.name || '') + '</strong>' + docLine +
                '<br><span>' + escapeHtml(src.org || '') +
                (pestHas(src.doc_type) ? ' · ' + escapeHtml(src.doc_type) : '') + '</span>' +
                link +
            '</div>';
        }).join('') + '</div>';
    }

    const note = Number(entry.is_verified) === 1
        ? '<p class="pest-refnote">本条已由农技人员复核。</p>'
        : '<p class="pest-refnote">本条依据公开技术资料编排，尚未经农技人员逐条复核，' +
          '仅供参考；实际防治请结合当地当期病虫情报。</p>';

    return '<section><h4 class="pest-block-title">' +
        '<i class="fas fa-book" aria-hidden="true"></i>数据来源</h4>' + inner + note + '</section>';
}

// ==================== 电商模块 ====================

function setupEventListeners() {
    // 电商模块卡片
    document.querySelectorAll('.module-card .btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const card = this.closest('.module-card');
            const module = card.dataset.module;
            if (module === 'live-stream') {
                document.getElementById('live-simulation').classList.remove('is-hidden');
                // 2026-10-05：商品标签改为下拉(#live-product)，打开时同步为当前全局作物
                syncLiveProductSelect();
                startLiveSimulation();
            } else if (module === 'product-copy') {
                openCopywritingPanel();
            } else if (module === 'customer-service') {
                openCustomerServicePanel();
            }
        });
    });

    document.getElementById('close-simulation')?.addEventListener('click', () => {
        document.getElementById('live-simulation').classList.add('is-hidden');
        stopLiveSimulation();
    });

    document.getElementById('generate-script')?.addEventListener('click', generateLiveScript);

    document.getElementById('copy-script')?.addEventListener('click', () => {
        const box = document.getElementById('live-script');
        const text = box?.innerText || '';
        if (text.trim()) {
            copyText(text, '话术已复制');
        }
    });

    // EC3：把 AI 初稿一键放进「我的稿」文本框，学员在此之上改写
    document.getElementById('adopt-script')?.addEventListener('click', () => {
        const src = document.getElementById('live-script');
        const dst = document.getElementById('live-script-mine');
        const text = (src?.innerText || '').trim();
        if (!text || /选择风格后点击/.test(text)) {
            showNotification('请先生成 AI 初稿', 'warning');
            return;
        }
        if (dst) {
            dst.value = text;
            dst.dispatchEvent(new Event('input'));
            dst.focus();
        }
        // P0-4：采用了新内容，旧评分失效
        resetLiveScorePanel();
        showNotification('已放入「我的稿」——补全【待填写】后再提交', 'success');
    });

    // 「我的稿」字数统计
    document.getElementById('live-script-mine')?.addEventListener('input', updateMyScriptCount);

    // EC3/EC4：朗读实录（麦克风 → 识别 → 可复现指标）
    document.getElementById('start-reading')?.addEventListener('click', startLiveReading);
    document.getElementById('stop-reading')?.addEventListener('click', stopLiveReading);
    document.getElementById('analyze-reading')?.addEventListener('click', analyzeLiveReading);

    // EC7：提交实训 + 实训记录
    document.getElementById('submit-live')?.addEventListener('click', submitLiveTraining);
    document.getElementById('toggle-live-records')?.addEventListener('click', () => {
        const panel = document.getElementById('live-records');
        if (!panel) return;
        const willShow = panel.classList.contains('is-hidden');
        panel.classList.toggle('is-hidden');
        if (willShow) loadLiveRecords();
    });
    document.getElementById('close-live-records')?.addEventListener('click', () => {
        document.getElementById('live-records')?.classList.add('is-hidden');
    });

    // 重新评分：EC3 —— 评的是「我的稿」，不是 AI 初稿
    document.getElementById('re-score-btn')?.addEventListener('click', () => {
        const text = currentMyScript();
        if (!text) {
            showNotification('请先在「我的稿」里写出你自己的话术', 'warning');
            return;
        }
        getLiveFeedback(text);
    });

    updateMyScriptCount();

    // 话术风格切换
    document.querySelectorAll('.style-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            document.querySelectorAll('.style-btn').forEach(b => b.classList.remove('active'));
            this.classList.add('active');
        });
    });

    // 直播间进阶（2026-10-05）：训练难度切换（下次「开始直播/开始朗读」生效，
    // 运行中切换不追溯已注入的突发状况）
    document.getElementById('live-difficulty')?.addEventListener('change', function() {
        LiveState.difficulty = this.value || '新手';
        showNotification('难度已切换为「' + LiveState.difficulty + '」', 'info');
    });

    // 2026-10-05：直播间内切换商品 —— 与顶部「选择农产品」双向联动。
    // 这里程序化触发对应顶部作物卡的 click，复用它的整条同步链
    // （AppState + localStorage + 农时日历 + 诊断/速查面板跟随），不另写一份同步逻辑。
    // 评论池/AI 弹幕/AI 话术/提交记录都在各自调用点实时读 AppState.currentProduct。
    // P1-1（2026-10-05 走查）：切换商品时**清空已生成内容**，否则学员把旧作物的稿子
    // 提交到新作物名下（名实不符）。有内容时先弹确认，防误触清空。
    document.getElementById('live-product')?.addEventListener('change', function() {
        const pid = this.value;
        if (!pid || pid === AppState.currentProduct) return;
        const card = document.querySelector('.product-card[data-product="' + pid + '"]');
        if (!card) { this.value = AppState.currentProduct || 'lychee'; return; }
        const prevProduct = AppState.currentProduct;
        const hasContent = currentMyScript() ||
            /(?:<p|AI|家人们|各位|宝子们|姐妹)/.test(
                (document.getElementById('live-script')?.innerText || '').trim());
        const doSwitch = function () {
            card.click();
            resetLiveContent();
            addLiveComment('系统', '已切换商品：' + getProductName(pid) +
                ' —— 观众提问和 AI 话术将跟随新品，记得重新生成初稿');
        };
        if (hasContent) {
            // 原生 confirm：阻断式确认，语义清晰，不额外引入弹窗组件
            if (window.confirm('切换商品会清空当前的 AI 初稿、我的稿、评分与朗读实录，确定切换吗？')) {
                doSwitch();
            } else {
                document.getElementById('live-product').value = prevProduct;
            }
        } else {
            doSwitch();
        }
    });
}

// P1-1：清空直播间所有已生成内容（切换商品时调用，防止跨作物名实不符）。
function resetLiveContent() {
    // AI 初稿框回到占位
    const scriptBox = document.getElementById('live-script');
    if (scriptBox) {
        scriptBox.innerHTML = '<div class="script-placeholder">' +
            '<i class="fas fa-magic"></i><p>选择风格后点击"生成 AI 初稿"</p></div>';
    }
    document.getElementById('script-degraded')?.classList.add('is-hidden');
    // 我的稿清空 + 字数归零 + 评分入口隐藏
    const mine = document.getElementById('live-script-mine');
    if (mine) { mine.value = ''; updateMyScriptCount(); }
    document.getElementById('re-score-btn')?.classList.add('is-hidden');
    // 评分面板复位
    document.getElementById('feedback-placeholder')?.classList.remove('is-hidden');
    document.getElementById('feedback-body')?.classList.add('is-hidden');
    const fm = document.getElementById('feedback-metrics');
    if (fm) fm.innerHTML = '';
    document.getElementById('feedback-suggestions')?.classList.add('is-hidden');
    document.getElementById('feedback-summary')?.classList.add('is-hidden');
    const src = document.getElementById('feedback-source');
    if (src) { src.classList.add('is-hidden'); src.innerHTML = ''; }
    // 朗读实录复位
    resetLiveReading();
    document.getElementById('reading-report-placeholder')?.classList.remove('is-hidden');
    document.getElementById('reading-report-body')?.classList.add('is-hidden');
    // 状态里的评分/报告一并清掉
    delete LiveState.lastFeedback;
    delete LiveState.lastReport;
}

// P0-4（学员端走查）：清掉「我的稿」的旧评分 —— 重新生成初稿 / 采用新内容后调用。
// 评分对象是「我的稿」；一旦稿子被替换，旧分必须清掉，否则「评分 → 重新生成 →
// 采用 → 提交」会把上一版稿子的分数连同新稿一起落库。
function resetLiveScorePanel() {
    delete LiveState.lastFeedback;
    delete LiveState.scoredScript;
    document.getElementById('feedback-placeholder')?.classList.remove('is-hidden');
    document.getElementById('feedback-body')?.classList.add('is-hidden');
    const fm = document.getElementById('feedback-metrics');
    if (fm) fm.innerHTML = '';
    document.getElementById('feedback-suggestions')?.classList.add('is-hidden');
    document.getElementById('feedback-summary')?.classList.add('is-hidden');
    const src = document.getElementById('feedback-source');
    if (src) { src.classList.add('is-hidden'); src.innerHTML = ''; }
}

// 打开直播间时把商品下拉同步为当前全局作物（唯一入口，防止下拉与全局口径脱节）
function syncLiveProductSelect() {
    const sel = document.getElementById('live-product');
    if (!sel) return;
    const pid = AppState.currentProduct || 'lychee';
    // 全局作物一定在 8 个白名单内；万一存储了未知值，下拉回退到荔枝
    sel.value = PRODUCT_NAMES[pid] ? pid : 'lychee';
}

// ==================== 直播模拟 ====================

const LiveState = {
    timer: null,
    seconds: 0,
    commentTimer: null,
    statTimer: null,
    introTimer: null,
    challengeTimer: null,   // 「挑战」难度的突发状况注入
    viewers: 0,
    likes: 0,
    comments: 0,
    isRunning: false,
    difficulty: '新手',     // 直播间进阶（2026-10-05）：新手/进阶/挑战
    pendingChallenge: null, // {text, at} 等待学员回应的突发状况
    // EC4：新增 —— 让直播间对学员的**实际表现**有反应
    speaking: false,        // 当前是否正在说话（由语音识别驱动）
    silenceSec: 0,          // 连续未说话秒数
    maxSilenceSec: 0,       // 本次最长冷场
    reading: false          // 是否已开始朗读（P3-6：冷场只在朗读后才统计）
};

// 「进阶/挑战」难度的质疑型评论池（与作物无关，砍价/质疑/要证据）。
// 直播间进阶（2026-10-05）：难度越高，从这里取评论的概率越大。
const LIVE_COMMENTS_HARD = [
    '别家更便宜，凭什么买你的？', '真有你说的那么好吗？', '包邮吗？不包邮就算了',
    '有农残检测报告吗？口说无凭', '上次买的水果坏了一半', '甜不甜啊？别是酸的吧',
    '能便宜点吗？贵了', '发什么快递？几天到？', '个头均匀吗？别图文不符',
    '支持退货吗？坏了怎么办？'
];

// 「挑战」难度会定期注入的突发状况；学员在 25 秒内给出安抚/解决方案可挽回观众。
const CHALLENGE_EVENTS = [
    '有观众刷屏：上次买的有一半是坏的！',
    '有观众说：别家同款比你便宜 20 块！',
    '有观众质疑：你说的新鲜，到手蔫了怎么办？',
    '有观众催：到底什么时候发货？说个准数！',
    '有观众问：你刚才说的优惠，链接里怎么没有？'
];

const LIVE_COMMENTS = {
    lychee: [
        '这个荔枝甜不甜？', '多少钱一箱？', '广东哪里的？', '包邮吗？',
        '能便宜点吗？', '发货快吗？', '有没有桂味？', '去年买过很好吃！',
        '可以送人吗？包装怎么样？', '荔枝新鲜吗？几天能到？', '来两箱！',
        '有没有试吃装？', '这个品种核大不大？', '冰袋保鲜吗？'
    ],
    longan: [
        '龙眼甜吗？', '肉厚不厚？', '哪里产的？', '几斤装？',
        '可以煲汤吗？', '新鲜的还是干的？', '来一箱试试',
        '去年买过不错', '发货快吗？', '有优惠吗？'
    ],
    // EC8：A3 把顶部作物补齐到 8 个之后，这里漏了柑橘与香蕉，
    // 会导致选柑橘开直播时评论池回退成荔枝（刷出「这个荔枝甜不甜？」）。
    citrus: [
        '是砂糖橘还是沃柑？', '甜不甜？', '酸不酸？', '皮薄吗？',
        '几斤装？', '哪里产的？', '有籽吗？', '什么时候上市？',
        '可以榨汁吗？', '发货快吗？', '有优惠吗？', '来一箱试试'
    ],
    banana: [
        '什么品种？', '香不香？', '是粉蕉还是香蕉？', '熟了吗？',
        '几斤装？', '哪里产的？', '怎么保存？', '放几天会坏？',
        '可以寄吗？', '有优惠吗？', '来一把试试', '甜不甜？'
    ],
    aquatic: [
        '鱼新鲜吗？', '怎么配送？', '什么品种？', '有没有刺少的？',
        '可以做酸菜鱼吗？', '几斤起卖？', '活鱼还是冰鲜？',
        '虾怎么卖？', '有没有套餐？', '顺丰冷链吗？'
    ],
    rice: [
        '什么品种？', '好吃吗？', '多少钱一斤？', '新米吗？',
        '煮饭香不香？', '有没有有机的？', '10斤装有吗？',
        '发货快吗？', '适合煮粥吗？', '产地哪里？'
    ],
    tea: [
        '什么茶？', '多少钱一斤？', '春茶还是秋茶？', '香不香？',
        '可以试喝吗？', '送人合适吗？', '泡出来什么颜色？',
        '有没有礼盒装？', '耐泡吗？', '回甘怎么样？'
    ],
    vegetable: [
        '有机的吗？', '怎么配送？', '新鲜吗？', '有农药残留吗？',
        '几斤起送？', '品种多吗？', '可以指定菜品吗？',
        '当天采摘吗？', '怎么保存？', '有没有套餐？'
    ]
};

// EC4：此前观众/点赞/评论是三个互不相干的随机数定时器 —— 学员说不说话，
// 数值都一模一样，直播间根本不构成「训练反馈」。现在改为：
//   · 观众只在开场阶段陆续进入；
//   · 之后完全由学员的表现驱动（说了互动指令→点赞评论涨；冷场→观众流失）。
const LIVE_USERS = ['小明', '阿花', '老王', '靓妹', '农家大姐', '吃货小李', '广东阿叔', '深圳打工仔', '佛山靓女', '潮汕老板'];

function liveCommentPool() {
    const product = AppState.currentProduct || 'lychee';
    return LIVE_COMMENTS[product] || LIVE_COMMENTS.lychee;
}

function liveRandomComment() {
    // 直播间进阶：难度决定「质疑型评论」混入比例（挑战 60% / 进阶 35% / 新手 0%）
    const diff = LiveState.difficulty || '新手';
    const hardRatio = diff === '挑战' ? 0.6 : (diff === '进阶' ? 0.35 : 0);
    let text;
    if (hardRatio > 0 && Math.random() < hardRatio) {
        text = LIVE_COMMENTS_HARD[Math.floor(Math.random() * LIVE_COMMENTS_HARD.length)];
    } else {
        const pool = liveCommentPool();
        text = pool[Math.floor(Math.random() * pool.length)];
    }
    return {
        user: LIVE_USERS[Math.floor(Math.random() * LIVE_USERS.length)],
        text: text
    };
}

function startLiveSimulation() {
    if (LiveState.isRunning) return;
    LiveState.isRunning = true;
    LiveState.seconds = 0;
    LiveState.viewers = 5;
    LiveState.likes = 0;
    LiveState.comments = 0;
    LiveState.speaking = false;
    LiveState.silenceSec = 0;
    LiveState.maxSilenceSec = 0;
    LiveState.pendingChallenge = null;
    LiveState.reading = false;   // P3-6：重新开始时重置朗读标志
    // 同步难度选择
    const diffSel = document.getElementById('live-difficulty');
    LiveState.difficulty = (diffSel && diffSel.value) || '新手';

    updateLiveStats();
    document.getElementById('live-badge')?.classList.add('active');

    // 计时器 + 冷场统计
    LiveState.timer = setInterval(() => {
        LiveState.seconds++;
        const mm = String(Math.floor(LiveState.seconds / 60)).padStart(2, '0');
        const ss = String(LiveState.seconds % 60).padStart(2, '0');
        const el = document.getElementById('live-duration');
        if (el) el.textContent = `${mm}:${ss}`;

        if (LiveState.speaking) {
            LiveState.silenceSec = 0;
        } else if (LiveState.reading) {
            // P3-6：只在「开始朗读」之后才做冷场统计 —— 生成初稿阶段学员还没开麦，
            // 不该把读稿准备时间记成「最长冷场」扣分。
            LiveState.silenceSec++;
            if (LiveState.silenceSec > LiveState.maxSilenceSec) {
                LiveState.maxSilenceSec = LiveState.silenceSec;
            }
            // 冷场超过 5 秒，观众开始流失
            if (LiveState.silenceSec % 5 === 0) {
                LiveState.viewers = Math.max(0, LiveState.viewers - 2);
                updateLiveStats();
            }
        }

        // 突发状况超时未回应 → 观众流失
        if (LiveState.pendingChallenge && Date.now() - LiveState.pendingChallenge.at > 25000) {
            addLiveComment('系统', '主播一直没有回应，有观众离开了…');
            LiveState.viewers = Math.max(0, LiveState.viewers - 4);
            updateLiveStats();
            LiveState.pendingChallenge = null;
        }
    }, 1000);

    // 观众陆续进入（仅开场的一段，之后完全由学员表现驱动）
    let entered = 0;
    LiveState.introTimer = setInterval(() => {
        entered++;
        LiveState.viewers += Math.floor(Math.random() * 4) + 1;
        updateLiveStats();
        if (entered >= 4) {
            clearInterval(LiveState.introTimer);
            LiveState.introTimer = null;
        }
    }, 1500);

    // 「挑战」难度：每 40~60 秒注入一条突发状况
    if (LiveState.difficulty === '挑战') {
        const inject = () => {
            if (!LiveState.isRunning) return;
            const evt = CHALLENGE_EVENTS[Math.floor(Math.random() * CHALLENGE_EVENTS.length)];
            addLiveComment('⚡ 突发状况', evt, true);   // 观众刷屏，计入评论数
            LiveState.pendingChallenge = { text: evt, at: Date.now() };
            LiveState.challengeTimer = setTimeout(inject, 40000 + Math.floor(Math.random() * 20000));
        };
        LiveState.challengeTimer = setTimeout(inject, 20000);
    }
}

function stopLiveSimulation() {
    LiveState.isRunning = false;
    clearInterval(LiveState.timer);
    clearInterval(LiveState.introTimer);
    clearInterval(LiveState.statTimer);
    clearInterval(LiveState.commentTimer);
    clearTimeout(LiveState.challengeTimer);
    LiveState.introTimer = null;
    LiveState.challengeTimer = null;
    LiveState.pendingChallenge = null;
    // P2-4（2026-10-05 走查）：朗读计时器 + 冷场状态一并清，避免先朗读再关弹窗后
    // 「分析朗读」的时长/冷场统计错乱。
    clearInterval(LiveReading.timer);
    LiveReading.timer = null;
    // P0-3（学员端走查）：关闭直播间必须同时停掉语音识别 —— 识别器的 onend 在
    // LiveReading.running 为真时会自动重启，只清 timer 会让麦克风一直被占用到刷新页面。
    LiveReading.running = false;
    try { LiveReading.recognition && LiveReading.recognition.stop(); } catch (err) { /* ignore */ }
    LiveReading.recognition = null;
    LiveState.speaking = false;
    LiveState.silenceSec = 0;
    _lastAiCommentAt = 0;  // 重置 AI 评论节流，避免跨场被 12s 节流卡住
    document.getElementById('live-badge')?.classList.remove('active');
}

function updateLiveStats() {
    const ve = document.getElementById('viewer-count');
    const le = document.getElementById('like-count');
    if (ve) ve.textContent = LiveState.viewers;
    if (le) le.textContent = LiveState.likes;
}

// count=true 表示该评论计入「评论数」统计（观众/突发状况）；系统提示（开播、切换商品、
// 超时流失）传 false，不计入。P3-7：把计数统一收进这里，避免调用处漏计导致列表与数字对不上。
function addLiveComment(user, text, count) {
    const container = document.getElementById('live-comments');
    if (!container) return;
    const div = document.createElement('div');
    div.className = 'comment-item comment-new';
    div.innerHTML = `<span class="comment-user">${user}：</span>${text}`;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
    if (count) {
        LiveState.comments++;
        const cc = document.getElementById('comment-count');
        if (cc) cc.textContent = LiveState.comments;
    }
    // 限制评论数量
    while (container.children.length > 30) container.firstChild.remove();
}

// ---- EC4：观众对学员所说内容的即时反应 --------------------------------------
// 命中不同类别的关键词，直播间给出不同反馈。这才是「模拟训练」的反馈回路：
// 学员能直观看到「说对了什么」带来了什么结果。
const LIVE_REACTIONS = [
    { re: /扣\s*\d|扣一|点个赞|点赞|关注|想要的|评论区|公屏/, like: 6, comment: true },
    { re: /价|元|块|钱|优惠|折扣|包邮|特价|划算/, like: 3, comment: true },
    { re: /斤|克|公斤|规格|果径|个头|品相|箱|装|份|袋/, like: 2, comment: true },
    { re: /甜|香|鲜|脆|嫩|糯|口感|风味|好吃|汁水/, like: 3, comment: true },
    { re: /广东|岭南|产地|原产|种植|养殖|果园|农场|产区/, like: 2, comment: true },
    { re: /售后|退|换|赔|保障|包退|包赔|放心|时效/, like: 2, comment: true }
];

function liveAudienceReact(text) {
    if (!text) return;

    // 「挑战」难度：突发状况的回应判定（安抚/给方案 → 观众回流；无视则在上面的
    // 计时器里按超时处理）
    if (LiveState.pendingChallenge &&
        /抱歉|对不起|包赔|包退|退换|补发|放心|一定|检测|报告|马上|立即|核实/.test(text)) {
        addLiveComment(LIVE_USERS[Math.floor(Math.random() * LIVE_USERS.length)],
            '主播回应挺快的，再看看', true);
        LiveState.viewers += 6;
        LiveState.likes += 10;
        LiveState.pendingChallenge = null;
        updateLiveStats();
    }

    const fired = LIVE_REACTIONS.filter(function (r) { return r.re.test(text); });
    if (!fired.length) {
        // 即使没命中卖点关键词，也试着让 AI 观众顺着话头发问（题库化）
        maybeAiComment(text);
        return;
    }

    let likes = 0;
    fired.forEach(function (r) {
        likes += r.like;
        if (r.comment) {
            const c = liveRandomComment();
            addLiveComment(c.user, c.text, true);
        }
    });
    LiveState.likes += likes;
    LiveState.viewers += Math.floor(fired.length / 2) + 1;   // 讲得对，有人留下来看
    updateLiveStats();

    maybeAiComment(text);
}

// ---- 直播间进阶（2026-10-05）·题库化：AI 按学员刚说的话生成针对性观众提问 ----
let _lastAiCommentAt = 0;
function maybeAiComment(speech) {
    if (!LiveState.isRunning) return;
    // 节流：至少间隔 12 秒，避免跟语音识别节奏打爆接口
    if (Date.now() - _lastAiCommentAt < 12000) return;
    _lastAiCommentAt = Date.now();
    // P3-8（2026-10-05 走查）：优先用累积的朗读全文，而不是当前识别片段，
    // 否则 AI 只看到半句话，提问会问串、上下文断裂。
    const full = (LiveReading.transcript || '').trim();
    const text = full || String(speech || '').trim();
    if (!text) return;
    apiCall('/api/ecommerce/live/comments', 'POST', {
        speech: text.slice(0, 200),
        product: getProductName(AppState.currentProduct || 'lychee'),
        difficulty: LiveState.difficulty || '新手'
    }).then(function (d) {
        if (d && d.success && d.comments) {
            d.comments.forEach(function (c) {
                addLiveComment(LIVE_USERS[Math.floor(Math.random() * LIVE_USERS.length)], c, true);
            });
        }
        // 失败/限流静默回退：规则评论池仍由 liveAudienceReact 的正常路径补充，
        // 不让「AI 不可用」打断训练。
    }).catch(function () { /* 静默：AI 评论是增强项，不是必需项 */ });
}

// ---- EC3/EC4：朗读实录（麦克风 → 识别 → 可复现指标）-------------------------
// 复用项目里已在方言语音问答使用过的 SpeechRecognition（无需新依赖）。
const LiveReading = {
    recognition: null,
    running: false,
    timer: null,
    seconds: 0,
    transcript: '',
    interim: '',
    lastResultAt: 0
};

function liveReadingSupport() {
    return !!(window.SpeechRecognition || window.webkitSpeechRecognition);
}

function resetLiveReading() {
    LiveReading.transcript = '';
    LiveReading.interim = '';
    LiveReading.seconds = 0;
    LiveReading.lastResultAt = 0;
    const t = document.getElementById('live-transcript-text');
    if (t) t.textContent = '（开始朗读后显示识别到的内容）';
    const tm = document.getElementById('reader-timer');
    if (tm) tm.textContent = '00:00';
}

function setMicStatus(status, hint) {
    const p = document.getElementById('mic-status');
    const h = document.getElementById('mic-hint');
    const ic = document.getElementById('mic-icon');
    if (p && status) p.textContent = status;
    if (h && hint !== undefined) h.textContent = hint;
    if (ic) ic.className = 'fas ' + (LiveReading.running ? 'fa-microphone-lines' : 'fa-microphone');
}

function startLiveReading() {
    if (LiveReading.running) return;
    if (!liveReadingSupport()) {
        showNotification('当前浏览器不支持语音识别，可改用文本方式练习', 'warning');
        setMicStatus('当前浏览器不支持语音识别',
            '建议用 Chrome / Edge；识别不可用时仍可提交「我的稿」做文本评分');
        return;
    }
    startLiveSimulation();
    resetLiveReading();
    LiveReading.running = true;
    LiveState.reading = true;   // P3-6：从这里才开始冷场统计

    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    const rec = new SR();
    rec.lang = 'zh-CN';
    rec.continuous = true;
    rec.interimResults = true;

    rec.onstart = function () {
        setMicStatus('正在聆听……请对着麦克风念你的话术', '识别有延迟，属正常现象');
    };
    rec.onresult = function (e) {
        let interim = '';
        for (let i = e.resultIndex; i < e.results.length; i++) {
            const r = e.results[i];
            if (r.isFinal) {
                LiveReading.transcript += r[0].transcript;
                liveAudienceReact(r[0].transcript);
            } else {
                interim += r[0].transcript;
            }
        }
        LiveReading.interim = interim;
        LiveReading.lastResultAt = Date.now();
        const t = document.getElementById('live-transcript-text');
        if (t) t.textContent = (LiveReading.transcript + interim) || '……';
        LiveState.speaking = true;
        LiveState.silenceSec = 0;
    };
    rec.onerror = function (e) {
        if (e.error === 'not-allowed' || e.error === 'service-not-allowed') {
            setMicStatus('麦克风权限被拒绝', '请在浏览器地址栏允许麦克风后重试');
        } else if (e.error === 'no-speech') {
            // 正常：一段时间没听到声音，交由冷场统计处理
        } else {
            setMicStatus('语音识别中断：' + e.error, '可点「结束朗读」后重新开始');
        }
    };
    rec.onend = function () {
        // continuous 模式下浏览器偶尔会自动结束；仍在朗读态则自动续上
        if (LiveReading.running) {
            try { rec.start(); } catch (err) { /* 已在运行则忽略 */ }
        }
    };

    try {
        rec.start();
    } catch (err) {
        LiveReading.running = false;
        showNotification('无法启动语音识别', 'error');
        return;
    }
    LiveReading.recognition = rec;

    LiveReading.timer = setInterval(function () {
        LiveReading.seconds++;
        const mm = String(Math.floor(LiveReading.seconds / 60)).padStart(2, '0');
        const ss = String(LiveReading.seconds % 60).padStart(2, '0');
        const tm = document.getElementById('reader-timer');
        if (tm) tm.textContent = mm + ':' + ss;
        // 识别有延迟：超过 2.5 秒没有新结果就视为「没在说话」
        if (LiveReading.lastResultAt && Date.now() - LiveReading.lastResultAt > 2500) {
            LiveState.speaking = false;
        }
    }, 1000);

    document.getElementById('start-reading')?.classList.add('is-hidden');
    document.getElementById('stop-reading')?.classList.remove('is-hidden');
}

function stopLiveReading() {
    LiveReading.running = false;
    clearInterval(LiveReading.timer);
    LiveReading.timer = null;
    try { LiveReading.recognition && LiveReading.recognition.stop(); } catch (err) { /* ignore */ }
    LiveReading.recognition = null;
    LiveState.speaking = false;
    LiveState.reading = false;   // P3-6：结束朗读后停止冷场统计
    setMicStatus('朗读已结束', '可点「分析朗读」查看完成度、语速与必卖点命中');
    document.getElementById('start-reading')?.classList.remove('is-hidden');
    document.getElementById('stop-reading')?.classList.add('is-hidden');
}

async function analyzeLiveReading() {
    const script = currentMyScript();
    const transcript = (LiveReading.transcript || '').trim();
    if (!script) { showNotification('请先写出「我的稿」', 'warning'); return; }
    if (!transcript) { showNotification('还没有识别到朗读内容，请先点「开始朗读」', 'warning'); return; }

    const placeholder = document.getElementById('reading-report-placeholder');
    const body = document.getElementById('reading-report-body');
    if (placeholder) placeholder.classList.add('is-hidden');
    if (body) body.classList.remove('is-hidden');

    try {
        const data = await apiCall('/api/ecommerce/live/report', 'POST', {
            script: script,
            transcript: transcript,
            duration_sec: LiveReading.seconds || LiveState.seconds,
            max_silence_sec: LiveState.maxSilenceSec
        });
        if (data.success) {
            renderReadingReport(data.report);
            LiveState.lastReport = data.report;
        } else {
            rollbackReadingReportPanel();
            showNotification(data.message || '分析失败', 'error');
        }
    } catch (e) {
        rollbackReadingReportPanel();
        showNotification('分析失败，请稍后重试', 'error');
    }
}

/* 朗读分析失败时把面板回滚到「未分析」态。旧实现先展开面板再请求，
   失败分支不回滚 → 留下一个空白报告面板，看起来像页面坏了。 */
function rollbackReadingReportPanel() {
    const placeholder = document.getElementById('reading-report-placeholder');
    const body = document.getElementById('reading-report-body');
    if (body) body.classList.add('is-hidden');
    if (placeholder) placeholder.classList.remove('is-hidden');
}

function renderReadingReport(rep) {
    if (!rep) return;
    LiveState.lastReport = rep;

    const overallEl = document.getElementById('reading-overall');
    if (overallEl) {
        const g = getScoreGrade(rep.overall_score);
        overallEl.textContent = rep.overall_score;
        overallEl.style.color = g.color;
    }

    const metrics = document.getElementById('reading-metrics');
    if (metrics) {
        const rows = [
            { label: '稿子完成度', value: rep.coverage + '%', icon: 'fa-check-double' },
            { label: '真实语速', value: rep.speed_cpm + ' 字/分', icon: 'fa-tachometer-alt' },
            { label: '必卖点命中', value: rep.rubric_hit + '/' + rep.rubric_total, icon: 'fa-bullseye' },
            { label: '最长冷场', value: rep.max_silence_sec + ' 秒', icon: 'fa-hourglass-half' }
        ];
        metrics.innerHTML = rows.map(function (r) {
            return '<div class="reading-metric"><label><i class="fas ' + r.icon + '"></i> ' +
                r.label + '</label><strong>' + r.value + '</strong></div>';
        }).join('');
    }

    const rubric = document.getElementById('reading-rubric');
    if (rubric && rep.rubric_items) {
        rubric.innerHTML = rep.rubric_items.map(function (it) {
            const cls = it.said ? 'hit' : (it.in_script ? 'missed' : 'absent');
            const icon = it.said ? 'fa-check-circle' : (it.in_script ? 'fa-exclamation-circle' : 'fa-times-circle');
            const note = it.said ? '已说出' : (it.in_script ? '稿里有、没说' : '稿里也缺');
            return '<span class="rubric-chip ' + cls + '"><i class="fas ' + icon + '"></i> ' +
                it.name + '<em>' + note + '</em></span>';
        }).join('');
    }

    const tips = document.getElementById('reading-tips');
    if (tips) {
        tips.innerHTML = (rep.tips || []).map(function (t) {
            return '<div class="reading-tip"><i class="fas fa-lightbulb"></i> ' + escapeHtml(t) + '</div>';
        }).join('') || '<div class="reading-tip"><i class="fas fa-check"></i> 没发现明显问题</div>';
    }
}

// ---- EC3/EC7：我的稿 / 提交实训 / 实训记录 ---------------------------------
function currentMyScript() {
    const el = document.getElementById('live-script-mine');
    return el ? (el.value || '').trim() : '';
}

function updateMyScriptCount() {
    const el = document.getElementById('live-script-mine');
    const meta = document.getElementById('my-script-count');
    if (!el || !meta) return;
    const n = (el.value || '').length;
    meta.textContent = n + ' 字';
    // 太短时给出提示色（只是视觉提示，不阻断提交）
    meta.classList.toggle('is-warn', n > 0 && n < 80);
    // EC3：评分入口跟随「我的稿」出现 —— 此前自动评分被移除后，
    // 重新评分按钮若仍等首次评分才显示，用户将永远找不到评分入口。
    const btn = document.getElementById('re-score-btn');
    if (n > 0) {
        btn?.classList.remove('is-hidden');
        // P1-2：评分入口出现时给一次脉冲动画，让学员注意到「要先评分」
        if (btn && !LiveState.lastFeedback) {
            btn.classList.remove('score-pulse');
            void btn.offsetWidth; // 强制重排以重启动画
            btn.classList.add('score-pulse');
        }
    }
}

async function submitLiveTraining() {
    const script = currentMyScript();
    if (!script) { showNotification('请先写出「我的稿」再提交', 'warning'); return; }
    // P1-2：还没评分就提交 → 明确引导（不阻断，但分数会记 0，提醒学员先评分）
    if (!LiveState.lastFeedback) {
        showNotification('提示：还没评分，提交后本稿分数暂记 0。建议先点右上角「重新评分」', 'warning');
    }
    // P0-4：评分只对「评分时的那一版我的稿」有效。若稿子已被改动，旧分不能算在新稿上。
    let feedbackToSend = LiveState.lastFeedback || {};
    if (LiveState.lastFeedback && LiveState.scoredScript !== script) {
        feedbackToSend = {};
        showNotification('提示：我的稿已改动，上次评分已失效，本次按 0 分提交。请重新评分', 'warning');
    }
    try {
        const data = await apiCall('/api/ecommerce/live/submit', 'POST', {
            product: getProductName(AppState.currentProduct || 'lychee'),
            script: script,
            feedback: feedbackToSend,
            report: LiveState.lastReport || {}
        });
        if (data.success) {
            showNotification('已保存实训记录（第 ' + data.attempts + ' 次）', 'success');
            loadLiveRecords();
        }
    } catch (e) {
        if (e && e.status === 401) {
            showNotification('保存失败：请先登录，登录后即可保存实训记录', 'warning', { actionLabel: '去登录', action: openLoginModal });
        } else if (e && e.status === 429) {
            showNotification('提交太频繁，请稍后再试', 'warning');
        } else {
            showNotification('保存失败，请稍后重试', 'error');
        }
    }
}

// 实训提交状态文案（与后端 app.py 的 _TRAINING_STATUS_LABELS 保持同口径）
// graded = 教师已批改；submitted = 待批改；resubmitted = 学员重新提交，教师需复核。
const TRAINING_STATUS_TEXT = {
    pending: '待提交',
    submitted: '待批改',
    graded: '已批改',
    resubmitted: '已重新提交·待复核'
};

async function loadLiveRecords() {
    const body = document.getElementById('live-records-body');
    if (!body) return;
    body.innerHTML = '<p class="records-empty">加载中…</p>';
    try {
        const data = await apiCall('/api/ecommerce/live/records', 'GET');
        if (!data.success) {
            body.innerHTML = '<p class="records-empty">登录后可保存并查看实训记录</p>';
            return;
        }
        const rows = data.records || [];
        if (!rows.length) {
            body.innerHTML = '<p class="records-empty">还没有实训记录 —— 写完「我的稿」后点「提交实训」</p>';
            return;
        }
        body.innerHTML = rows.map(function (r) {
            const rep = r.report || {};
            const st = TRAINING_STATUS_TEXT[r.status] || '待批改';
            const teacherTxt = (r.score === null || r.score === undefined) ? '待老师批改' : (r.score + ' 分');
            const ruleTxt = (r.rule_score === null || r.rule_score === undefined) ? '—' : (r.rule_score + ' 分');
            return '<div class="record-item">' +
                '<div class="record-head"><strong>' + escapeHtml(r.product || '') + '</strong>' +
                '<span class="record-score">教师评分 ' + teacherTxt + '</span></div>' +
                '<div class="record-meta">第 ' + (r.attempts || 1) + ' 次 · ' +
                escapeHtml(r.submitted_at || '') +
                ' · ' + st + ' · 系统规则分 ' + ruleTxt + '</div>' +
                (rep.coverage !== undefined
                    ? '<div class="record-meta">完成度 ' + rep.coverage + '% · 语速 ' + rep.speed_cpm +
                      ' 字/分 · 必卖点 ' + rep.rubric_hit + '/' + rep.rubric_total +
                      (rep.overall_score !== undefined ? ' · 朗读分 ' + rep.overall_score : '') + '</div>'
                    : '') +
                (r.feedback ? '<div class="record-feedback">教师评语：' + escapeHtml(r.feedback) + '</div>' : '') +
                '</div>';
        }).join('');
    } catch (e) {
        body.innerHTML = '<p class="records-empty">登录后可保存并查看实训记录</p>';
    }
}

// 通用实训记录加载（2026-10-05 文案/客服闭环）：与 loadLiveRecords 同一接口，kind 区分。
function loadTrainingRecords(kind, bodyId) {
    const body = document.getElementById(bodyId);
    if (!body) return;
    body.innerHTML = '<p class="records-empty">加载中…</p>';
    apiCall('/api/ecommerce/live/records?kind=' + encodeURIComponent(kind), 'GET')
        .then(function (data) {
            if (!data.success) {
                body.innerHTML = '<p class="records-empty">登录后可保存并查看实训记录</p>';
                return;
            }
            const rows = data.records || [];
            if (!rows.length) {
                body.innerHTML = '<p class="records-empty">还没有实训记录</p>';
                return;
            }
            body.innerHTML = rows.map(function (r) {
                const meta = r.meta || {};
                const extras = [];
                if (meta.format) extras.push(meta.format);
                if (meta.scenario) extras.push(meta.scenario);
                if (meta.difficulty) extras.push(meta.difficulty);
                const st = TRAINING_STATUS_TEXT[r.status] || '待批改';
                // score = 教师批改分；rule_score = 系统规则分（提交时按规则算出，仅作参考）
                const teacherTxt = (r.score === null || r.score === undefined) ? '待老师批改' : (r.score + ' 分');
                const ruleTxt = (r.rule_score === null || r.rule_score === undefined) ? '—' : (r.rule_score + ' 分');
                return '<div class="record-item">' +
                    '<div class="record-head"><strong>' + escapeHtml(r.product || '') + '</strong>' +
                    '<span class="record-score">教师评分 ' + teacherTxt + '</span></div>' +
                    '<div class="record-meta">第 ' + (r.attempts || 1) + ' 次 · ' +
                    escapeHtml(r.submitted_at || '') +
                    (extras.length ? ' · ' + escapeHtml(extras.join(' · ')) : '') +
                    ' · ' + st + ' · 系统规则分 ' + ruleTxt + '</div>' +
                    (r.feedback ? '<div class="record-feedback">教师评语：' + escapeHtml(r.feedback) + '</div>' : '') +
                    '</div>';
            }).join('');
        })
        .catch(function () {
            body.innerHTML = '<p class="records-empty">登录后可保存并查看实训记录</p>';
        });
}

async function generateLiveScript() {
    const scriptContent = document.getElementById('live-script');
    const style = document.querySelector('.style-btn.active')?.dataset.style || '热情';
    // 2026-10-05：商品标签已改为下拉(#live-product)，商品名以直播间内下拉为准
    // （下拉值与全局作物双向联动，但生成时显式读下拉，保证所见即所得）。
    const productSel = document.getElementById('live-product');
    const product = (productSel && productSel.value) || AppState.currentProduct || 'lychee';
    const productName = getProductName(product);

    const degradedEl = document.getElementById('script-degraded');
    if (degradedEl) degradedEl.classList.add('is-hidden');

    showSkeleton(scriptContent, 'text', 5);
    // P0-4：重新生成初稿后上一版稿子的评分已失效，必须清掉（见 resetLiveScorePanel）
    resetLiveScorePanel();
    startLiveSimulation();

    try {
        const data = await apiCall('/api/ecommerce/script', 'POST', { product: productName, style });
        if (data.success) {
            scriptContent.innerHTML = '<p style="white-space:pre-line;" id="script-typewriter"></p>';
            const tw = document.getElementById('script-typewriter');
            await typewriterEffect(tw, data.script);
            // EC5：上游不可用时服务端会下发 degraded，明确标注"非 AI 生成"
            if (data.degraded && degradedEl) degradedEl.classList.remove('is-hidden');
            showNotification(`${style}风格初稿已生成，记得改写成你自己的稿`, 'success');
            // EC3：不再自动评分 —— 评分对象是「我的稿」，由学员改写后主动触发
        } else {
            showNotification(data.message || '生成失败', 'error');
        }
    } catch(e) {
        // 失败必须可见：先提示，再给出「系统内置示例」，并用角标说明这不是 AI 生成的
        let msg = '生成失败，请稍后重试';
        if (/429/.test(String(e && e.message))) msg = '请求过于频繁，请稍后再试';
        else if (/400/.test(String(e && e.message))) msg = '当前产品/风格暂不支持';
        showNotification(msg, 'warning');

        const fallbackScripts = {
            '热情': `家人们！今天给你们带来广东的${productName}！\n(互动) 想要的扣1，让我看看有多少人识货！\n你们看这个品相，颜色鲜亮、个头匀称，【待填写：按你手上产品的真实外观描述】。\n今天的优惠价是【待填写：直播间价格】，另有【待填写：本场优惠形式，如满减/赠品】。\n(引导) 觉得值的给我点个赞，【待填写：本场互动活动】！\n【待填写：库存或数量说明】，想要的朋友抓紧下单！`,
            '专业': `各位朋友好，今天给大家带来的是广东${productName}。\n【待填写：具体产地/产区】，【待填写：品种特性与种植方式】。\n我们每一批都【待填写：检测项目与报告情况】，检测报告大家可以看屏幕。\n和市面上普通产品相比，我们的优势在于【待填写：规格、等级等真实差异】。\n今天直播间优惠，【待填写：优惠形式与到手价】，性价比很高。`,
            '故事': `在广东的一个村子，有人种了多年${productName}。\n他常说："好东西急不得，要等天时、靠地利、更要用心。"\n(停顿) 到了收获的时候，天不亮就要下地，只为赶在太阳出来前把最新鲜的一批采下来。\n从枝头到你手里，【待填写：采摘与发货时效】——这是我们想做到的事。\n今天把这份来自岭南的风味带给大家，【待填写：口感与品质的真实描述】。\n(引导) 想尝尝的，点下方链接下单吧。`,
            '高级': `岭南夏日，最令人期待的，莫过于这口来自广东的${productName}。\n它生长在【待填写：产区】，【待填写：气候与风土描述】。\n【待填写：口感与品质的真实描述】，入口的细腻是大自然的馈赠。\n岭南风物，如今一键下单便可抵达你的餐桌。\n今日【待填写：供应与规格说明】，自用送礼皆宜。\n品味不将就，生活要讲究。`
        };
        const txt = fallbackScripts[style] || fallbackScripts['热情'];
        scriptContent.innerHTML = `<p style="white-space:pre-line;">${txt}</p>`;
        if (degradedEl) degradedEl.classList.remove('is-hidden');
        // EC3：兜底时同样不自动评分
    }
}

// 评分维度配置
const METRIC_LABELS = {
    speed_score: { label: '语速节奏', icon: 'fa-tachometer-alt' },
    emotion_score: { label: '情绪感染力', icon: 'fa-heart' },
    interaction_score: { label: '互动技巧', icon: 'fa-comments' },
    selling_score: { label: '卖点提炼', icon: 'fa-bullseye' }
};

function getScoreGrade(score) {
    if (score >= 90) return { text: 'S', color: '#1f5e43', label: '优秀' };
    if (score >= 80) return { text: 'A', color: '#2f6b4f', label: '良好' };
    if (score >= 70) return { text: 'B', color: '#d9a227', label: '中等' };
    if (score >= 60) return { text: 'C', color: '#f97316', label: '及格' };
    return { text: 'D', color: '#ef4444', label: '需改进' };
}

function getScoreColor(score) {
    if (score >= 85) return '#1f5e43';
    if (score >= 70) return '#2f6b4f';
    if (score >= 55) return '#d9a227';
    return '#ef4444';
}

function renderFeedbackMetrics(metrics) {
    const container = document.getElementById('feedback-metrics');
    if (!container) return;
    container.innerHTML = '';
    const keys = Object.keys(METRIC_LABELS);
    // 直播间进阶（2026-10-05）：AI 每维度给 evidence（引用原文的一句话依据），
    // 随分数展示，让学员知道「分从哪来」；规则路径无 evidence 则只显示分数条。
    const evidence = (metrics && metrics.evidence) || null;
    keys.forEach((key, i) => {
        const score = metrics[key] || 0;
        const config = METRIC_LABELS[key];
        const color = getScoreColor(score);
        const evText = evidence ? (evidence[key] || '') : '';
        const div = document.createElement('div');
        div.className = 'metric';
        div.innerHTML = `
            <div class="metric-row">
                <label><i class="fas ${config.icon}"></i> ${config.label}</label>
                <div class="progress-bar"><div class="progress-fill" id="fb-${key}" style="width:0%"></div></div>
                <span id="fb-${key}-val" style="color:${color}">-</span>
            </div>
            ${evText ? `<div class="metric-evidence"><i class="fas fa-quote-left"></i> ${escapeHtml(evText)}</div>` : ''}
        `;
        container.appendChild(div);
        // 延迟动画
        setTimeout(() => animateScore(`fb-${key}`, `fb-${key}-val`, score), i * 150);
    });
}

// 基于话术内容分析生成差异化分数
// EC2（2026-10-05）：这里原有一层 Math.random() 抖动，导致同一段稿子每次评分都不一样
// （实测 80/81/78），且它属于「测评类功能」—— 测评必须可复现，故整块去掉随机。
// 注意：本函数只在「服务端评分接口不可用」时作为本地兜底，正常路径应由服务端给分。
function analyzeScript(text) {
    const exclamation = (text.match(/[！!]{1,}/g) || []).length;
    const question = (text.match(/[？?]{1,}/g) || []).length;
    const interactionWords = (text.match(/扣\d|点[个一]赞|觉得值|想要的|有没有|是不是|对不对|家人们|宝子们/g) || []).length;
    const pauseMarks = (text.match(/停顿|稍等|\.\.\.|\…/g) || []).length;
    const dataMarks = (text.match(/\d+[%°度]|【[^】]+】|\d+[元斤箱份]/g) || []).length;
    const emotionWords = (text.match(/太[香好吃棒]|绝了|真的|必须|一定要|超级|特别|非常/g) || []).length;
    const priceWords = (text.match(/原价|划线价|专属价|只要|仅需|优惠|折扣|限量|最后|手慢无/g) || []).length;

    let speed = 68 + Math.min(pauseMarks * 6, 20) + Math.min(exclamation * 2, 10);
    let emotion = 65 + Math.min(emotionWords * 5, 20) + Math.min(exclamation * 3, 15) + Math.min(question * 2, 10);
    let interaction = 60 + Math.min(interactionWords * 8, 30) + Math.min(question * 3, 10);
    let selling = 66 + Math.min(dataMarks * 5, 20) + Math.min(priceWords * 4, 16);

    speed = Math.min(98, Math.max(50, speed));
    emotion = Math.min(98, Math.max(50, emotion));
    interaction = Math.min(98, Math.max(50, interaction));
    selling = Math.min(98, Math.max(50, selling));

    return { speed_score: speed, emotion_score: emotion, interaction_score: interaction, selling_score: selling };
}

// 基于内容和分数生成针对性建议
function generateScriptSuggestions(text, scores) {
    const suggestions = [];
    const hasInteraction = /扣\d|点[个一]赞|觉得值/.test(text);
    const hasPause = /停顿|\.\.\./.test(text);
    const hasData = /\d+[元斤箱度%]/.test(text);
    const hasPrice = /原价|只要|专属价/.test(text);
    const hasEmotion = /家人们|宝子们|太[香好吃]/.test(text);

    if (scores.interaction_score < 75 && !hasInteraction) {
        suggestions.push('加入互动指令，如"想要的扣1""觉得值的点个赞"');
    }
    if (scores.speed_score < 72 && !hasPause) {
        suggestions.push('适当加入停顿，制造悬念感，如"(停顿3秒)"');
    }
    if (scores.selling_score < 75 && !hasData) {
        suggestions.push('把产品特点讲具体：真实规格、检测指标等；缺数据处用【待填写】标注，不要编数字');
    }
    if (scores.emotion_score < 72 && !hasEmotion) {
        suggestions.push('增加情绪词和感叹句，如"这也太香了吧！"');
    }
    if (!hasPrice) {
        suggestions.push('补上价格信息：按你产品的真实售价填写，不要虚构原价或划线价');
    }
    if (scores.selling_score >= 75 && scores.interaction_score >= 75) {
        suggestions.push('整体不错，可以尝试讲故事增加情感共鸣');
    }

    const general = [
        '开场3秒内抛出核心卖点抓住注意力',
        '表达紧迫感用"数量有限/限时"即可，不要虚构原价与优惠力度',
        '加入真实的用户好评或复购情况增强信任，没有就不要编',
        '结尾引导关注直播间获取更多优惠',
        '用对比法突出产品差异化优势，对比对象须为真实同类产品'
    ];
    // EC2：不再 shuffle —— 建议顺序固定，便于学员与教师对照复现
    let gi = 0;
    while (suggestions.length < 3 && gi < general.length) {
        suggestions.push(general[gi++]);
    }
    return suggestions.slice(0, 3);
}

async function getLiveFeedback(script) {
    const placeholder = document.getElementById('feedback-placeholder');
    const body = document.getElementById('feedback-body');
    const overallEl = document.getElementById('feedback-overall');
    const scoreEl = document.getElementById('overall-score');
    const gradeEl = document.getElementById('overall-grade');
    const suggestionsEl = document.getElementById('feedback-suggestions');
    const suggestionsList = document.getElementById('suggestions-list');
    const summaryEl = document.getElementById('feedback-summary');
    const reScoreBtn = document.getElementById('re-score-btn');
    const sourceEl = document.getElementById('feedback-source');

    if (placeholder) placeholder.classList.add('is-hidden');
    if (body) body.classList.remove('is-hidden');
    if (reScoreBtn) reScoreBtn.classList.remove('is-hidden');
    if (sourceEl) { sourceEl.classList.add('is-hidden'); sourceEl.innerHTML = ''; }

    // 清空并显示加载
    const metricsContainer = document.getElementById('feedback-metrics');
    if (metricsContainer) {
        metricsContainer.innerHTML = Array(4).fill('<div class="metric skeleton-metric"></div>').join('');
    }
    if (scoreEl) { scoreEl.textContent = '...'; scoreEl.style.color = 'var(--text-muted)'; }
    if (gradeEl) { gradeEl.textContent = '分析中'; gradeEl.style.background = 'var(--border-light)'; }

    try {
        const data = await apiCall('/api/ecommerce/feedback', 'POST', { script });
        if (data.success) {
            const f = data.feedback;
            // 关键：把评分结果存进 LiveState.lastFeedback —— 提交实训时要把分数一起落库，
            // 且后续「未评分就提交」的提示、切换商品时的清空判断都依赖它。
            LiveState.lastFeedback = f;
            LiveState.scoredScript = script;   // P0-4：记录评分对应的稿子
            renderFeedbackMetrics(f);

            // 综合评分
            const overall = f.overall_score || Math.round((f.speed_score + f.emotion_score + f.interaction_score + f.selling_score) / 4);
            const grade = getScoreGrade(overall);
            if (scoreEl) {
                animateNumber(scoreEl, overall, 1000);
                scoreEl.style.color = grade.color;
            }
            if (gradeEl) {
                setTimeout(() => {
                    gradeEl.textContent = `${grade.text} · ${grade.label}`;
                    gradeEl.style.background = grade.color;
                }, 600);
            }

            // 建议
            if (f.suggestions && f.suggestions.length > 0) {
                if (suggestionsEl) suggestionsEl.classList.remove('is-hidden');
                if (suggestionsList) {
                    suggestionsList.innerHTML = f.suggestions.map((s, i) =>
                        `<span class="suggestion-tag" style="animation-delay:${i * 0.1}s"><i class="fas fa-check-circle"></i> ${s}</span>`
                    ).join('');
                }
            }

            // 总结
            if (summaryEl && f.summary) {
                summaryEl.classList.remove('is-hidden');
                summaryEl.innerHTML = `<i class="fas fa-comment-dots"></i> ${f.summary}`;
            }

            // EC2：如实标注本次分数来源（AI 评分 / 规则评分）——字段在 feedback 对象内
            renderFeedbackSource(sourceEl, f.source, f.source_note);
        } else {
            // 失败必须可见：不渲染兜底分数，直接告知失败原因
            showNotification(data.message || '评分失败', 'error');
            if (placeholder) placeholder.classList.remove('is-hidden');
            if (body) body.classList.add('is-hidden');
            if (reScoreBtn) reScoreBtn.classList.add('is-hidden');
        }
    } catch(e) {
        const errMsg = String((e && e.message) || '');
        // 限流：明确告知，不伪装成"服务不可用"
        if (/429/.test(errMsg)) {
            if (placeholder) placeholder.classList.remove('is-hidden');
            if (body) body.classList.add('is-hidden');
            if (reScoreBtn) reScoreBtn.classList.add('is-hidden');
            showNotification('请求过于频繁，请稍后再试', 'warning');
            return;
        }
        // 基于话术内容分析生成差异化分数
        const analyzed = analyzeScript(script);
        renderFeedbackMetrics(analyzed);

        const overall = Math.round(Object.values(analyzed).reduce((a, b) => a + b, 0) / 4);
        // 本地兜底评分同样写入 lastFeedback，保证提交时分数能落库（来源标注为 rule）
        LiveState.lastFeedback = Object.assign({}, analyzed, {
            overall_score: overall,
            source: 'rule',
            source_note: '服务端暂时不可用，以上为浏览器端规则分析结果（可复现，非 AI 评分）'
        });
        LiveState.scoredScript = script;
        const grade = getScoreGrade(overall);
        if (scoreEl) {
            animateNumber(scoreEl, overall, 1000);
            scoreEl.style.color = grade.color;
        }
        if (gradeEl) {
            setTimeout(() => {
                gradeEl.textContent = `${grade.text} · ${grade.label}`;
                gradeEl.style.background = grade.color;
            }, 600);
        }

        // 基于内容生成针对性建议
        const suggestions = generateScriptSuggestions(script, analyzed);
        if (suggestionsEl) suggestionsEl.classList.remove('is-hidden');
        if (suggestionsList) {
            suggestionsList.innerHTML = suggestions.map((s, i) =>
                `<span class="suggestion-tag" style="animation-delay:${i * 0.1}s"><i class="fas fa-check-circle"></i> ${s}</span>`
            ).join('');
        }
        // 如实说明：这是本地兜底，不是 AI 评分
        renderFeedbackSource(sourceEl, 'rule',
            '服务端暂时不可用，以上为浏览器端规则分析结果（可复现，非 AI 评分）');
    }
}

// EC2：分数来源标签（服务端下发 source / source_note，前端如实展示，不美化）
function renderFeedbackSource(el, source, note) {
    if (!el) return;
    const map = {
        ai: { cls: 'is-ai', icon: 'fa-robot', text: 'AI 评分' },
        rule: { cls: 'is-rule', icon: 'fa-calculator', text: '规则评分' }
    };
    const meta = map[source];
    const text = note || (meta ? '' : '');
    if (!meta && !text) { el.classList.add('is-hidden'); return; }
    const head = meta ? ('<i class="fas ' + meta.icon + '"></i> ' + meta.text) : '';
    el.className = 'feedback-source' + (meta ? ' ' + meta.cls : '');
    el.innerHTML = head + (text ? '<span>' + escapeHtml(text) + '</span>' : '');
}

function animateScore(fillId, valId, target) {
    const fill = document.getElementById(fillId);
    const val = document.getElementById(valId);
    if (!fill) return;
    fill.style.transition = 'width 0.8s cubic-bezier(0.4, 0, 0.2, 1)';
    requestAnimationFrame(() => { fill.style.width = target + '%'; });
    if (val) {
        let current = 0;
        const step = Math.max(1, Math.floor(target / 30));
        const interval = setInterval(() => {
            current = Math.min(current + step, target);
            val.textContent = current + '分';
            if (current >= target) clearInterval(interval);
        }, 25);
    }
}

// 清理（2026-10-05 小清理项）：此处原有一个 `animateNumber` 重复声明
// （本文件尾部另有一个同名函数，JS 中后声明者恒覆盖前者，故此处为死代码）。
// 已删除，统一使用尾部版本。

// ==================== 电商新面板 ====================

const COPY_PRESETS = {
    lychee: { name: '荔枝', points: '甜度高、果肉厚、核小、产地直发、冷链保鲜', audiences: ['水果爱好者', '送礼人群', '家庭采购'] },
    longan: { name: '龙眼', points: '肉厚核小、甜而不腻、煲汤佳品、补气养血', audiences: ['养生人群', '煲汤爱好者', '送礼人群'] },
    rice: { name: '水稻', points: '软糯香甜、新米直发、有机种植、颗粒饱满', audiences: ['家庭主妇', '注重健康人群', '餐饮商家'] },
    tea: { name: '茶叶', points: '高山茶园、手工炒制、回甘持久、礼盒包装', audiences: ['茶友', '商务送礼', '养生人群'] },
    vegetable: { name: '蔬菜', points: '有机种植、当天采摘、无农残、产地直发', audiences: ['注重健康人群', '家庭采购', '餐饮商家'] },
    aquatic: { name: '水产', points: '鲜活直发、肉质鲜美、冷链配送、干净无腥', audiences: ['海鲜爱好者', '家庭烹饪', '餐饮商家'] }
};

function openCopywritingPanel() {
    const preset = COPY_PRESETS[AppState.currentProduct] || COPY_PRESETS.lychee;
    showDetailModal('商品文案创作', `
        <div class="copywriting-panel">
            <div class="copy-stepper" id="copy-stepper">
                <div class="copy-step" data-step="1"><span class="copy-step-dot">1</span><span class="copy-step-label">配置</span></div>
                <div class="copy-step-line"></div>
                <div class="copy-step" data-step="2"><span class="copy-step-dot">2</span><span class="copy-step-label">生成</span></div>
                <div class="copy-step-line"></div>
                <div class="copy-step" data-step="3"><span class="copy-step-dot">3</span><span class="copy-step-label">改写</span></div>
                <div class="copy-step-line"></div>
                <div class="copy-step" data-step="4"><span class="copy-step-dot">4</span><span class="copy-step-label">评分提交</span></div>
            </div>

            <div class="copy-config">
                <div class="copy-config-row">
                    <div class="form-group">
                        <label><i class="fas fa-box"></i> 产品名称 <span class="hint">（限平台支持的农产品）</span></label>
                        <input type="text" id="copy-product" placeholder="例如：荔枝（可选：龙眼/柑橘/香蕉/水稻/茶叶/蔬菜/水产养殖）" value="${preset.name}">
                    </div>
                    <div class="form-group">
                        <label><i class="fas fa-users"></i> 目标人群</label>
                        <select id="copy-audience">
                            <option value="">不限</option>
                            ${preset.audiences.map(a => `<option value="${a}">${a}</option>`).join('')}
                        </select>
                    </div>
                </div>
                <div class="form-group">
                    <label><i class="fas fa-star"></i> 核心卖点 <span class="hint">（用逗号分隔，留空自动生成）</span></label>
                    <input type="text" id="copy-points" placeholder="例如：甜度高、果肉厚、核小" value="${preset.points}">
                </div>
            </div>

            <div class="copy-formats">
                <label class="form-label"><i class="fas fa-file-alt"></i> 选择文案格式</label>
                <div class="format-tabs" id="format-tabs">
                    <button class="format-tab active" data-format="详情页"><i class="fas fa-list-alt"></i> 详情页</button>
                    <button class="format-tab" data-format="主图文案"><i class="fas fa-image"></i> 主图文案</button>
                    <button class="format-tab" data-format="朋友圈"><i class="fab fa-weixin"></i> 朋友圈</button>
                    <button class="format-tab" data-format="小红书"><i class="fas fa-book-open"></i> 小红书</button>
                    <button class="format-tab" data-format="短视频脚本"><i class="fas fa-film"></i> 短视频</button>
                </div>
                <div class="format-desc" id="format-desc">电商商品详情页文案，层次分明，卖点突出</div>
            </div>

            <div class="copy-actions">
                <button class="btn btn-primary" id="generate-copywriting-btn">
                    <i class="fas fa-magic"></i> AI生成文案
                </button>
                <button class="btn btn-outline btn-sm" id="regenerate-copy-btn" style="display:none;">
                    <i class="fas fa-redo"></i> 换一版
                </button>
            </div>

            <div id="copywriting-result"></div>

            <!-- 文案实训闭环（2026-10-05）：AI 只出初稿，学员改写后提交「我的稿」 -->
            <div class="script-block copy-mine-block" style="margin-top:16px;" id="copy-mine-block">
                <div class="script-block-title" id="copy-mine-head" style="cursor:pointer;">
                    <i class="fas fa-pen"></i> 我的稿
                    <span class="script-block-sub">（把 AI 初稿改写成你自己的版本后提交）</span>
                    <span class="copy-stage-badge" id="copy-stage-badge">待生成</span>
                    <span class="script-block-meta" id="copy-mine-count">0 字</span>
                </div>
                <div class="copy-mine-body" id="copy-mine-body">
                <div class="copy-placeholder-bar" id="copy-placeholder-bar" style="display:none;">
                    <i class="fas fa-flag"></i> 还有 <b id="copy-placeholder-count">0</b> 处【待填写】未补全
                </div>
                <textarea id="copy-mine" class="script-input" rows="8" maxlength="4000"
                    placeholder="用「采用到我的稿」把 AI 初稿放进来，再补上【待填写】里的真实信息、换成你自己的语气……"></textarea>
                <div class="script-block-note">
                    认证、检测数据、价格、物流与赔付承诺不能靠 AI 编 —— 没有真实信息就保持占位或删除该句。
                </div>
                <div class="script-actions script-actions-submit">
                    <button class="btn btn-outline btn-sm" id="adopt-copy"><i class="fas fa-arrow-down"></i> 采用到我的稿</button>
                    <button class="btn btn-outline btn-sm" id="copy-score-btn"><i class="fas fa-chart-bar"></i> 评分</button>
                    <button class="btn btn-primary btn-sm" id="submit-copy"><i class="fas fa-paper-plane"></i> 提交实训</button>
                </div>
                </div>
                <div class="copy-feedback" id="copy-feedback" style="display:none;">
                    <div class="copy-feedback-head">
                        <span class="copy-feedback-overall" id="copy-feedback-overall">-</span>
                        <span class="copy-feedback-label">文案评分（规则 · 可复现）</span>
                    </div>
                    <div class="copy-feedback-metrics" id="copy-feedback-metrics"></div>
                    <div class="copy-feedback-suggestions" id="copy-feedback-suggestions"></div>
                </div>
                <div class="training-submit-info" id="copy-submit-info"></div>
            </div>
            <div class="live-records" id="copy-records" style="margin-top:12px;">
                <div class="records-header">
                    <h4><i class="fas fa-list"></i> 我的文案实训记录</h4>
                </div>
                <div class="records-body" id="copy-records-body">
                    <p class="records-empty">登录后可保存并查看实训记录</p>
                </div>
            </div>
        </div>
    `);

    // 文案实训：字数统计 + 采用 + 提交 + 记录（与直播实训同一套作业链路，kind=copy）
    const copyMineEl = document.getElementById('copy-mine');

    // P2-4（2026-10-05 走查）：保存最近一次生成的原始 markdown 文本，
    // 「采用到我的稿」用它而非 innerText（innerText 会丢失 **加粗** 和列表符号）。
    let lastRawCopy = '';
    // P1-2（2026-10-05）：文案评分闭环 —— 规则评分、可复现，评「我的稿」。
    // 评分结果存 copyScore，提交时随 score 落库（对齐直播实训的评分能力）。
    let copyScore = null;
    let copyScoreScript = '';   // P0-4：记录评分对应的文案内容

    // ===== 体验优化（2026-10-05）：步骤条 + 状态驱动 + 待填写高亮 =====
    // 环节状态：生成前折叠「我的稿」，生成后展开；评分后高亮「评分提交」。
    let copyHasGenerated = false;   // 是否已成功生成过初稿
    const setCopyStep = (step) => {
        document.querySelectorAll('#copy-stepper .copy-step').forEach(s => {
            const n = parseInt(s.dataset.step, 10);
            s.classList.toggle('active', n === step);
            s.classList.toggle('done', n < step);
        });
    };
    const setCopyStage = (hasText, scored) => {
        const badge = document.getElementById('copy-stage-badge');
        if (badge) {
            if (scored) { badge.textContent = '已评分'; badge.className = 'copy-stage-badge stage-scored'; }
            else if (hasText) { badge.textContent = '已改写'; badge.className = 'copy-stage-badge stage-edited'; }
            else if (copyHasGenerated) { badge.textContent = '待改写'; badge.className = 'copy-stage-badge stage-pending'; }
            else { badge.textContent = '待生成'; badge.className = 'copy-stage-badge stage-pending'; }
        }
    };
    const refreshCopyStage = () => {
        const hasText = (copyMineEl?.value || '').trim().length > 0;
        const scored = !!copyScore;
        // 步骤条：生成前停在「配置」，生成后推进到「改写」，评分后推进到「评分提交」
        if (!copyHasGenerated && !hasText) setCopyStep(1);
        else if (scored) setCopyStep(4);
        else if (hasText) setCopyStep(3);
        else setCopyStep(2);
        setCopyStage(hasText, scored);
        // 评分/提交按钮状态驱动
        const scoreBtn = document.getElementById('copy-score-btn');
        const submitBtn = document.getElementById('submit-copy');
        if (scoreBtn) scoreBtn.disabled = !hasText;
        if (submitBtn) submitBtn.disabled = !hasText;
    };
    const updateCopyCount = () => {
        if (!copyMineEl) return;
        const val = copyMineEl.value || '';
        const n = val.length;
        document.getElementById('copy-mine-count').textContent = n + ' 字';
        // 待填写残留计数（体验优化）：统计【待填写...】占位符数量
        // （兼容「【待填写】」和「【待填写：说明文字】」两种形态）
        const phCount = (val.match(/【待填写[^】]*】/g) || []).length;
        const bar = document.getElementById('copy-placeholder-bar');
        if (bar) {
            bar.style.display = phCount > 0 ? 'flex' : 'none';
            document.getElementById('copy-placeholder-count').textContent = phCount;
        }
        refreshCopyStage();
    };
    copyMineEl?.addEventListener('input', updateCopyCount);
    updateCopyCount();

    // 体验优化（2026-10-05）：折叠交互 + 初始折叠状态。
    // 生成前「我的稿」折叠（避免空表单干扰），生成后自动展开。
    const mineBody = document.getElementById('copy-mine-body');
    const mineHead = document.getElementById('copy-mine-head');
    if (mineHead && mineBody) {
        mineHead.addEventListener('click', () => {
            const hidden = mineBody.style.display === 'none';
            mineBody.style.display = hidden ? 'block' : 'none';
        });
        mineBody.style.display = 'none';   // 初始折叠
    }

    // P0-4：清掉「我的稿」的旧评分（重新生成初稿 / 采用新内容后调用），
    // 否则步骤条停在「已评分」、提交时把旧分算到新文案上。
    const resetCopyScore = () => {
        copyScore = null;
        copyScoreScript = '';
        const box = document.getElementById('copy-feedback');
        if (box) box.style.display = 'none';
        const cmp = document.getElementById('copy-compare');
        if (cmp) cmp.style.display = 'none';
        refreshCopyStage();
    };

    document.getElementById('adopt-copy')?.addEventListener('click', () => {
        const text = (lastRawCopy || '').trim();
        if (!text) { showNotification('请先生成 AI 初稿', 'warning'); return; }
        copyMineEl.value = text;
        copyMineEl.dispatchEvent(new Event('input'));
        copyMineEl.focus();
        // P0-4：采用了新内容，旧评分失效
        resetCopyScore();
        // 体验优化：采用后滚动到「我的稿」，并高亮待填写提示
        setTimeout(() => {
            const bar = document.getElementById('copy-placeholder-bar');
            if (bar && bar.style.display !== 'none') {
                bar.classList.add('copy-placeholder-pulse');
                setTimeout(() => bar.classList.remove('copy-placeholder-pulse'), 1600);
            }
            const block = document.getElementById('copy-mine-block');
            if (block && block.scrollIntoView) block.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }, 100);
        showNotification('已放入「我的稿」——补全真实信息后再提交', 'success');
    });

    // P1-2（2026-10-05）：文案评分闭环 —— 规则评分、可复现，评「我的稿」。
    const renderCopyFeedback = (fb) => {
        const box = document.getElementById('copy-feedback');
        if (!box) return;
        box.style.display = 'block';
        const overall = document.getElementById('copy-feedback-overall');
        const g = getScoreGrade(fb.overall_score);
        overall.textContent = fb.overall_score;
        overall.style.color = g.color;
        const metrics = document.getElementById('copy-feedback-metrics');
        const rows = [
            { label: '结构完整', key: 'structure_score', icon: 'fa-list-alt' },
            { label: '卖点具体', key: 'selling_score', icon: 'fa-bullseye' },
            { label: '格式契合', key: 'format_score', icon: 'fa-file-alt' },
            { label: '合规自检', key: 'compliance_score', icon: 'fa-shield-alt' }
        ];
        metrics.innerHTML = rows.map(r => {
            const v = fb[r.key] || 0;
            const c = getScoreColor(v);
            return '<div class="copy-feedback-metric"><label><i class="fas ' + r.icon + '"></i> ' +
                r.label + '</label><div class="progress-bar"><div class="progress-fill" style="width:' + v + '%"></div></div>' +
                '<em style="color:' + c + '">' + v + '</em></div>';
        }).join('');
        const sug = document.getElementById('copy-feedback-suggestions');
        sug.innerHTML = (fb.suggestions || []).map(s =>
            '<div class="copy-feedback-tip"><i class="fas fa-lightbulb"></i> ' + escapeHtml(s) + '</div>').join('');
    };
    // 体验优化（2026-10-05）：AI 初稿 vs 我的稿 评分对比。
    // 学员改写后，把两份稿的规则评分并列展示，直观看到「改写得如何」。
    const renderCopyCompare = (mine, ai) => {
        let box = document.getElementById('copy-compare');
        if (!box) {
            const fb = document.getElementById('copy-feedback');
            box = document.createElement('div');
            box.id = 'copy-compare';
            box.className = 'copy-compare';
            fb.parentNode.insertBefore(box, fb);
        }
        const grade = (v) => getScoreGrade(v);
        const card = (title, icon, fbObj, cls) => {
            const v = fbObj && fbObj.overall_score != null ? fbObj.overall_score : null;
            const g = v != null ? grade(v) : { color: 'var(--text-muted)', label: '未评分' };
            const delta = '';
            return '<div class="copy-compare-card ' + cls + '">' +
                '<div class="copy-compare-head"><i class="fas ' + icon + '"></i>' + title + '</div>' +
                '<div class="copy-compare-score" style="color:' + g.color + '">' + (v != null ? v : '-') + '</div>' +
                '<div class="copy-compare-label">' + (v != null ? '规则评分' : '尚未评分') + '</div>' +
            '</div>';
        };
        box.innerHTML = card('AI 初稿', 'fa-robot', ai, 'copy-compare-ai') +
            '<div class="copy-compare-vs">VS</div>' +
            card('我的稿', 'fa-pen', mine, 'copy-compare-mine');
        box.style.display = 'flex';
    };
    document.getElementById('copy-score-btn')?.addEventListener('click', async () => {
        const script = (copyMineEl?.value || '').trim();
        if (!script) { showNotification('请先在「我的稿」里写出你的文案', 'warning'); return; }
        const btn = document.getElementById('copy-score-btn');
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 评分中...';
        try {
            const data = await apiCall('/api/ecommerce/copy/feedback', 'POST', {
                script: script, format: currentFormat
            });
            if (data.success) {
                copyScore = data.feedback;
                copyScoreScript = script;
                renderCopyFeedback(data.feedback);
                refreshCopyStage();
                // 体验优化：若有 AI 初稿，异步评分初稿做对比（不影响我的稿评分展示）
                if (lastRawCopy && lastRawCopy.trim()) {
                    try {
                        const aiData = await apiCall('/api/ecommerce/copy/feedback', 'POST', {
                            script: lastRawCopy.trim(), format: currentFormat
                        });
                        if (aiData.success) renderCopyCompare(data.feedback, aiData.feedback);
                    } catch (e2) { /* 对比失败静默，不影响主评分 */ }
                }
            }
        } catch (e) {
            showNotification('评分失败，请稍后重试', 'error');
        } finally {
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-chart-bar"></i> 评分';
        }
    });

    document.getElementById('submit-copy')?.addEventListener('click', async () => {
        const script = (copyMineEl?.value || '').trim();
        if (!script) { showNotification('请先在「我的稿」里写出你自己的文案', 'warning'); return; }
        // P1-2：未评分就提交 → 温和提示（不阻断）
        if (!copyScore) {
            showNotification('提示：还没评分，提交后本稿分数暂记 0。建议先点「评分」', 'warning');
        }
        // P0-4：评分只对「评分时的那一版我的稿」有效；我的稿已改动则旧分不计入
        if (copyScore && copyScoreScript !== script) {
            showNotification('提示：我的稿已改动，上次评分已失效，本次按 0 分提交。请重新评分', 'warning');
        }
        const info = document.getElementById('copy-submit-info');
        try {
            // P2-3（2026-10-05 走查）：产品名「名实不符」问题。文案产品名是自由文本
            // （学员可填「增城桂味荔枝」），但后端落库按 8 作物白名单校验。
            // 这里把「归属作物」用全局当前作物（保证过白名单、记录口径一致），
            // 学员填的具体产品名放进 meta 留痕，不丢失。
            const rawProduct = (document.getElementById('copy-product').value || '').trim();
            const data = await apiCall('/api/ecommerce/copy/submit', 'POST', {
                product: getProductName(AppState.currentProduct || 'lychee'),
                script: script,
                score: (copyScore && copyScoreScript === script) ? copyScore.overall_score : 0,
                meta: { format: currentFormat, raw_product: rawProduct }
            });
            if (data.success) {
                if (info) info.textContent = '已保存实训记录（第 ' + data.attempts + ' 次）';
                showNotification('已保存实训记录（第 ' + data.attempts + ' 次）', 'success');
                loadTrainingRecords('copy', 'copy-records-body');
            }        } catch (e) {
            if (e && e.status === 401) showNotification('保存失败：请先登录', 'warning', { actionLabel: '去登录', action: openLoginModal });
            else showNotification('保存失败，请稍后重试', 'error');
        }
    });

    loadTrainingRecords('copy', 'copy-records-body');

    // 格式切换
    const formatDescs = {
        '详情页': '电商商品详情页文案，层次分明，卖点突出',
        '主图文案': '5条独立主图文案，每条8-15字，简洁有力',
        '朋友圈': '微信朋友圈推广文案，真实自然，像朋友分享',
        '小红书': '小红书种草笔记，种草感强，闺蜜推荐风格',
        '短视频脚本': '15-30秒短视频带货脚本，按时间轴输出'
    };
    let currentFormat = '详情页';
    // P3-6（2026-10-05 走查）：format-desc 初始值单一来源 —— 面板打开即用
    // formatDescs 同步一次，消除 HTML 里硬编码的重复文案。
    const descEl0 = document.getElementById('format-desc');
    if (descEl0) descEl0.textContent = formatDescs[currentFormat] || '';

    document.querySelectorAll('.format-tab').forEach(tab => {
        tab.addEventListener('click', function() {
            document.querySelectorAll('.format-tab').forEach(t => t.classList.remove('active'));
            this.classList.add('active');
            currentFormat = this.dataset.format;
            document.getElementById('format-desc').textContent = formatDescs[currentFormat] || '';
        });
    });

    // 生成文案
    const generateBtn = document.getElementById('generate-copywriting-btn');
    const regenBtn = document.getElementById('regenerate-copy-btn');
    const resultDiv = document.getElementById('copywriting-result');

    // P3-5（2026-10-05 走查）：区分「首次生成」与「换一版」的 loading 反馈。
    async function generate(isRegen) {
        const product = document.getElementById('copy-product').value.trim();
        if (!product) { showNotification('请输入产品名称', 'warning'); return; }

        const audience = document.getElementById('copy-audience').value;
        const selling_points = document.getElementById('copy-points').value.trim();

        showSkeleton(resultDiv, 'text', 5);
        generateBtn.disabled = true;
        generateBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 生成中...';
        if (isRegen && regenBtn) {
            regenBtn.disabled = true;
            regenBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 换一版中...';
        }

        try {
            const data = await apiCall('/api/ecommerce/copywriting', 'POST', {
                product, format: currentFormat, audience, selling_points
            });
            if (data.success) {
                // P1-1（2026-10-05 走查）：上游失败时服务端下发 degraded + 兜底文案，
                // 必须像直播脚本一样明确标注「非 AI 生成」，否则学员会把【待填写】兜底当成 AI 成果。
                const degradedTag = data.degraded
                    ? '<span class="copy-degraded-tag"><i class="fas fa-exclamation-triangle"></i> 系统内置示例 · 非 AI 生成</span>'
                    : '';
                resultDiv.innerHTML = `
                    <div class="copy-result">
                        <div class="copy-result-header">
                            <span class="copy-result-tag"><i class="fas fa-file-alt"></i> ${currentFormat}</span>
                            ${degradedTag}
                            <div class="copy-result-actions">
                                <button class="btn btn-outline btn-sm" id="copy-result-md-btn"><i class="fab fa-markdown"></i> 复制 Markdown</button>
                                <button class="btn btn-outline btn-sm" id="copy-result-btn"><i class="fas fa-copy"></i> 复制</button>
                            </div>
                        </div>
                        <div class="copy-result-body" id="copy-result-body"></div>
                    </div>
                `;
                // 体验优化（2026-10-05）：状态推进不等 typewriter（纯视觉打字效果），
                // 生成成功即刻推进步骤、展开「我的稿」，避免长文案打字期间界面停在「配置」。
                copyHasGenerated = true;
                const mineBody = document.getElementById('copy-mine-body');
                if (mineBody) mineBody.style.display = 'block';
                lastRawCopy = data.copywriting || '';   // P2-4：保存原始文本供「采用」（打字期间也可采用）
                // P0-4：生成了新初稿，上一版我的稿的评分失效
                resetCopyScore();
                refreshCopyStage();

                const body = document.getElementById('copy-result-body');
                await typewriterEffect(body, data.copywriting);
                body.innerHTML = formatAnswer(data.copywriting);

                document.getElementById('copy-result-btn')?.addEventListener('click', () => {
                    copyText(data.copywriting, '文案已复制');
                });
                document.getElementById('copy-result-md-btn')?.addEventListener('click', () => {
                    copyText(data.copywriting, '已复制 Markdown 原文');
                });

                regenBtn.style.display = 'inline-flex';

                // 滚动到结果区，让学员看到产物
                const res = document.querySelector('.copy-result');
                if (res && res.scrollIntoView) {
                    setTimeout(() => res.scrollIntoView({ behavior: 'smooth', block: 'nearest' }), 150);
                }
            }
        } catch(e) {
            // P1-10：区分「产品名不在白名单」这类 400 —— 重试无用，必须说清原因。
            // 此前一律「生成失败，请重试」，学员照着旧的占位示例（自由文本产品名）填，
            // 会反复失败却不知为何，还会被「重试」误导。
            if (e && e.code === 'unknown_product') {
                showErrorState(resultDiv, '产品名称不在支持范围：请从 荔枝 / 龙眼 / 柑橘 / 香蕉 / 水稻 / 茶叶 / 蔬菜 / 水产养殖 中选择', () => generate(false));
            } else if (e && e.code === 'rate_limited') {
                showErrorState(resultDiv, '请求过于频繁，请稍后再试', () => generate(false));
            } else {
                showErrorState(resultDiv, '生成失败，请重试', () => generate(false));
            }
        } finally {
            generateBtn.disabled = false;
            generateBtn.innerHTML = '<i class="fas fa-magic"></i> AI生成文案';
            if (regenBtn) {
                regenBtn.disabled = false;
                regenBtn.innerHTML = '<i class="fas fa-redo"></i> 换一版';
            }
        }
    }

    generateBtn?.addEventListener('click', () => generate(false));
    regenBtn?.addEventListener('click', () => generate(true));
}


function openCustomerServicePanel() {
    const productName = getProductName(AppState.currentProduct);
    showDetailModal('客户服务模拟', `
        <div class="cs-panel">
            <div class="cs-config">
                <div class="cs-config-row">
                    <div class="form-group">
                        <label><i class="fas fa-theater-masks"></i> 模拟场景</label>
                        <select id="cs-scenario">
                            <option value="售前咨询">售前咨询</option>
                            <option value="售后处理">售后处理</option>
                            <option value="投诉应对">投诉应对</option>
                            <option value="议价谈判">议价谈判</option>
                            <option value="产品推荐">产品推荐</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label><i class="fas fa-user"></i> 客户性格</label>
                        <select id="cs-personality">
                            <option value="友善型">友善型 · 好说话</option>
                            <option value="急躁型">急躁型 · 没耐心</option>
                            <option value="犹豫型">犹豫型 · 反复比较</option>
                            <option value="挑剔型">挑剔型 · 要求高</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label><i class="fas fa-signal"></i> 难度</label>
                        <select id="cs-difficulty">
                            <option value="新手">新手 · 简单</option>
                            <option value="进阶" selected>进阶 · 适中</option>
                            <option value="挑战">挑战 · 困难</option>
                        </select>
                    </div>
                </div>
                <div class="cs-config-row">
                    <div class="form-group">
                        <label><i class="fas fa-box"></i> 产品</label>
                        <input type="text" id="cs-product" value="${productName}">
                    </div>
                    <div class="form-group" style="flex:1;">
                        <label><i class="fas fa-play-circle"></i> 操作</label>
                        <div class="cs-actions">
                            <button class="btn btn-primary btn-sm" id="cs-start-btn"><i class="fas fa-play"></i> 开始模拟</button>
                            <button class="btn btn-outline btn-sm" id="cs-reset-btn"><i class="fas fa-redo"></i> 重置</button>
                            <button class="btn btn-outline btn-sm" id="cs-hint-btn"><i class="fas fa-lightbulb"></i> 提示</button>
                        </div>
                    </div>
                </div>
            </div>

            <div class="cs-chat-area">
                <div class="cs-chat-main">
                    <div class="cs-messages" id="cs-messages">
                        <div class="cs-welcome">
                            <i class="fas fa-headset"></i>
                            <p>选择场景和客户性格，点击"开始模拟"进行客服训练</p>
                            <div class="cs-mission-card" id="cs-mission-card" style="display:none;"></div>
                        </div>
                    </div>
                    <div class="cs-input-bar">
                        <input type="text" id="cs-input" placeholder="作为客服回复客户..." disabled>
                        <button class="btn btn-primary" id="cs-send-btn" disabled><i class="fas fa-paper-plane"></i></button>
                    </div>
                    <!-- 体验优化③：内联参考话术 chip，点击填入输入框 -->
                    <div class="cs-quick-chips" id="cs-quick-chips" style="display:none;"></div>
                </div>
                <div class="cs-sidebar">
                    <div class="cs-score-card" id="cs-score-card">
                        <h4><i class="fas fa-chart-radar"></i> 实时评分</h4>
                        <div class="cs-score-note" id="cs-score-note">规则关键词评分 · 逐句分析，提交取整场均分</div>
                        <div class="cs-score-overall" id="cs-score-overall">-</div>
                        <div class="cs-score-label">综合得分</div>
                        <div class="cs-score-bars" id="cs-score-bars">
                            <div class="cs-score-bar" id="cs-bar-polite">
                                <span>礼貌度</span>
                                <div class="progress-bar"><div class="progress-fill" id="cs-polite" style="width:0%"></div></div>
                                <em id="cs-polite-val">-</em>
                            </div>
                            <div class="cs-score-bar" id="cs-bar-pro">
                                <span>专业度</span>
                                <div class="progress-bar"><div class="progress-fill" id="cs-pro" style="width:0%"></div></div>
                                <em id="cs-pro-val">-</em>
                            </div>
                            <div class="cs-score-bar" id="cs-bar-solve">
                                <span>解决力</span>
                                <div class="progress-bar"><div class="progress-fill" id="cs-solve" style="width:0%"></div></div>
                                <em id="cs-solve-val">-</em>
                            </div>
                            <div class="cs-score-bar" id="cs-bar-empathy">
                                <span>同理心</span>
                                <div class="progress-bar"><div class="progress-fill" id="cs-empathy" style="width:0%"></div></div>
                                <em id="cs-empathy-val">-</em>
                            </div>
                        </div>
                        <!-- 体验优化②：最弱维度高亮 + 可行动建议 -->
                        <div class="cs-weak-hint" id="cs-weak-hint" style="display:none;"></div>
                    </div>
                    <div class="cs-tips-card" id="cs-tips-card">
                        <h4><i class="fas fa-lightbulb"></i> 实时建议</h4>
                        <div class="cs-tips-list" id="cs-tips-list">
                            <div class="cs-tip-item">开始对话后将显示建议</div>
                        </div>
                    </div>
                    <!-- 体验优化⑥：客户情绪温度条（随每轮回复质量变化） -->
                    <div class="cs-sentiment-card" id="cs-sentiment-card">
                        <h4><i class="fas fa-smile"></i> 客户情绪</h4>
                        <div class="cs-sentiment-label" id="cs-sentiment-label">待开始</div>
                        <div class="cs-sentiment-track">
                            <div class="cs-sentiment-fill" id="cs-sentiment-fill" style="width:60%;"></div>
                        </div>
                        <div class="cs-sentiment-scale"><span>不满</span><span>满意</span></div>
                    </div>
                    <div class="cs-history-card">
                        <h4><i class="fas fa-history"></i> 对话轮次</h4>
                        <div class="cs-round-count" id="cs-round-count">0 轮</div>
                        <!-- 客服实训闭环（2026-10-05）：对话记录提交进作业链路，kind=cs -->
                        <button class="btn btn-outline btn-sm" id="cs-submit-btn" style="margin-top:10px;">
                            <i class="fas fa-paper-plane"></i> 提交实训
                        </button>
                        <div class="training-submit-info" id="cs-submit-info"></div>
                    </div>
                    <div class="cs-history-card">
                        <h4><i class="fas fa-list"></i> 我的实训记录</h4>
                        <div class="records-body" id="cs-records-body" style="max-height:220px;">
                            <p class="records-empty">登录后可保存并查看实训记录</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `);

    const chatHistory = [];
    let isStarted = false;
    // P1-1（2026-10-06 走查）：提交分数改为「整场所有轮次的平均分」，而非最后一句。
    // lastCsScore 仅用于实时展示最近一轮；csScoreHistory 累计每一轮，提交时取平均。
    let lastCsScore = 0;
    const csScoreHistory = [];
    // 体验优化⑤（2026-10-06）：每轮明细（分数+文本+提示），供复盘卡取「高光时刻/待改进点」。
    const csRoundDetails = [];
    // 体验优化⑥（2026-10-06）：客户情绪温度条当前值（0-100）。
    let csSentiment = 60;

    const startBtn = document.getElementById('cs-start-btn');
    const resetBtn = document.getElementById('cs-reset-btn');
    const hintBtn = document.getElementById('cs-hint-btn');
    const sendBtn = document.getElementById('cs-send-btn');
    const chatInput = document.getElementById('cs-input');
    const messagesDiv = document.getElementById('cs-messages');

    // 体验优化④（2026-10-06）：场景任务卡——开始前动态说明任务目标。
    const MISSION = {
        '售前咨询': '耐心解答产品信息，让客户放心下单',
        '售后处理': '先安抚情绪，再给出可落地的解决方案',
        '投诉应对': '稳住客户情绪，把投诉转为可解决的动作',
        '议价谈判': '在不失底线的前提下促成成交',
        '产品推荐': '摸清客户需求，精准推荐合适的产品'
    };
    const PERSONA_HINT = {
        '友善型': '客户好说话，正常专业即可',
        '急躁型': '客户没耐心，回复要快、直给重点',
        '犹豫型': '客户反复比较，多给信心和证据',
        '挑剔型': '客户爱挑细节，把专业做扎实'
    };
    const updateMissionCard = () => {
        const card = document.getElementById('cs-mission-card');
        if (!card) return;
        const scenario = document.getElementById('cs-scenario').value;
        const personality = document.getElementById('cs-personality').value;
        const difficulty = document.getElementById('cs-difficulty').value;
        card.style.display = 'block';
        card.innerHTML = `
            <div class="cs-mission-row"><span class="cs-mission-tag">${scenario}</span><span class="cs-mission-tag">${personality}</span><span class="cs-mission-tag">${difficulty}</span></div>
            <div class="cs-mission-goal"><i class="fas fa-flag-checkered"></i> 你的目标：${MISSION[scenario] || MISSION['售前咨询']}</div>
            <div class="cs-mission-persona">${PERSONA_HINT[personality] || ''}</div>
        `;
    };
    ['cs-scenario', 'cs-personality', 'cs-difficulty'].forEach(id => {
        document.getElementById(id)?.addEventListener('change', updateMissionCard);
    });
    updateMissionCard();

    // 开始模拟
    startBtn?.addEventListener('click', async () => {
        const scenario = document.getElementById('cs-scenario').value;
        const personality = document.getElementById('cs-personality').value;
        const product = document.getElementById('cs-product').value.trim() || '农产品';

        messagesDiv.innerHTML = '';
        chatHistory.length = 0;
        isStarted = true;
        chatInput.disabled = false;
        sendBtn.disabled = false;
        chatInput.placeholder = `场景：${scenario} | 你是客服，请回复客户...`;
        startBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 生成中...';
        startBtn.disabled = true;

        try {
            const data = await apiCall('/api/ecommerce/customer-service/next', 'POST', {
                scenario, personality, product, history: []
            });
            if (data.success) {
                appendCSMsg('customer', data.message);
                chatHistory.push({ role: 'assistant', content: data.message });
                if (data.degraded) {
                    const dnote = document.createElement('div');
                    dnote.className = 'cs-degraded-note';
                    dnote.innerHTML = '<i class="fas fa-exclamation-triangle"></i> 系统兜底开场白（非 AI 生成）';
                    messagesDiv.appendChild(dnote);
                }
                chatInput.focus();
            }
        } catch(e) {
            // P2-4（2026-10-06 走查）：开始失败必须可见，不能静默塞一句假开场白。
            let msg = '生成开场白失败，请稍后重试';
            if (e && (e.status === 429 || /429/.test(String(e && e.message)))) msg = '操作过于频繁，请稍后再试';
            showNotification(msg, 'error');
            // 回滚「开始」状态，让学员可重新点开始
            isStarted = false;
            chatInput.disabled = true;
            sendBtn.disabled = true;
            messagesDiv.innerHTML = `
                <div class="cs-welcome">
                    <i class="fas fa-exclamation-circle"></i>
                    <p>开场白生成失败，请重试「开始模拟」</p>
                </div>`;
        } finally {
            startBtn.innerHTML = '<i class="fas fa-play"></i> 开始模拟';
            startBtn.disabled = false;
        }
    });

    // 发送消息
    async function sendMsg() {
        const msg = chatInput.value.trim();
        if (!msg || !isStarted) return;
        chatInput.value = '';

        // 先渲染学员气泡（无得分），评分返回后补得分徽标
        const agentDiv = appendCSMsg('agent', msg);

        const scenario = document.getElementById('cs-scenario').value;
        const personality = document.getElementById('cs-personality').value;
        const difficulty = document.getElementById('cs-difficulty').value;
        const product = document.getElementById('cs-product').value.trim() || '农产品';

        // 显示打字指示器
        const typingDiv = document.createElement('div');
        typingDiv.className = 'cs-msg customer cs-typing-msg';
        typingDiv.innerHTML = '<div class="cs-msg-bubble"><div class="typing-dots"><span></span><span></span><span></span></div></div>';
        messagesDiv.appendChild(typingDiv);
        messagesDiv.scrollTop = messagesDiv.scrollHeight;

        try {
            // history不包含当前消息，当前消息作为message单独传
            const data = await apiCall('/api/ecommerce/customer-service', 'POST', {
                message: msg, history: chatHistory, scenario, personality, difficulty, product
            });
            typingDiv.remove();
            if (data.success) {
                appendCSMsg('customer', data.reply);
                // 先存用户消息，再存AI回复，保持交替顺序
                chatHistory.push({ role: 'user', content: msg });
                chatHistory.push({ role: 'assistant', content: data.reply });

                // P1-1（学员端走查）：AI 不可用时后端会下发 degraded，必须如实告知学员，
                // 否则学员以为在跟 AI 客户练，实际拿到的是规则兜底。
                if (data.degraded) {
                    const dnote = document.createElement('div');
                    dnote.className = 'cs-degraded-note';
                    dnote.innerHTML = '<i class="fas fa-exclamation-triangle"></i> 系统兜底回复（非 AI 生成，仅供参考）';
                    messagesDiv.appendChild(dnote);
                    messagesDiv.scrollTop = messagesDiv.scrollHeight;
                }

                // 更新评分：实时展示最近一轮，累计所有轮次供提交取平均
                if (data.score && typeof data.score.total === 'number') {
                    lastCsScore = data.score.total;
                    csScoreHistory.push(data.score.total);
                    // 体验优化⑤：记录每轮明细（供复盘卡取高光时刻/待改进点）
                    csRoundDetails.push({ score: data.score.total, text: msg, tips: data.score.tips || [] });
                    updateCSScore(data.score);
                    // 体验优化①：给刚渲染的学员气泡补得分徽标 + 扣分原因
                    if (agentDiv) {
                        const label = agentDiv.querySelector('.cs-msg-label');
                        if (label) {
                            const s = data.score.total;
                            const grade = s >= 85 ? 'good' : s >= 70 ? 'mid' : s >= 55 ? 'warn' : 'bad';
                            label.insertAdjacentHTML('beforeend',
                                ` <span class="cs-msg-score cs-score-${grade}">${s}分</span>`);
                        }
                        if (data.score.tips && data.score.tips.length) {
                            const reason = document.createElement('div');
                            reason.className = 'cs-msg-reason';
                            reason.textContent = data.score.tips[0];
                            agentDiv.querySelector('.cs-msg-content').appendChild(reason);
                        }
                    }
                }

                // 体验优化⑥：更新客户情绪温度条
                if (data.sentiment) {
                    csSentiment = data.sentiment.level;
                    updateCSSentiment(data.sentiment);
                }

                // 更新轮次
                const rounds = Math.floor(chatHistory.length / 2);
                document.getElementById('cs-round-count').textContent = `${rounds} 轮`;
            }
        } catch(e) {
            // P1-3 + P2-5（2026-10-06 走查）：失败必须可见，且不得污染对话历史。
            // 原实现把一句假的客户回复塞进 chatHistory 并显示，既冒充 AI 又污染提交记录。
            typingDiv.remove();
            // 撤回已经渲染的学员气泡？不——学员这句保留，但要明确标注「未得到客户回应」。
            let msg = '回复失败，请稍后重试';
            if (e && (e.status === 429 || /429/.test(String(e && e.message)))) msg = '对话过于频繁，请稍后再试';
            else if (e && e.status === 400) msg = '内容不合法，请调整后重试';
            showNotification(msg, 'error');
            // 在消息流里追加一条可见的错误占位（不进入 chatHistory，不冒充客户）
            appendCSError('客户未回应：' + (e && e.status === 429 ? '请求过于频繁' : '网络或服务异常，请重试'));
            chatInput.focus();
        }
    }

    sendBtn?.addEventListener('click', sendMsg);
    chatInput?.addEventListener('keydown', e => { if (e.key === 'Enter') sendMsg(); });

    // 重置
    resetBtn?.addEventListener('click', () => {
        messagesDiv.innerHTML = `
            <div class="cs-welcome">
                <i class="fas fa-headset"></i>
                <p>选择场景和客户性格，点击"开始模拟"进行客服训练</p>
                <div class="cs-mission-card" id="cs-mission-card" style="display:none;"></div>
            </div>
        `;
        chatHistory.length = 0;
        isStarted = false;
        // P3-9（2026-10-06 走查）：重置时清空评分状态，避免残留旧分。
        lastCsScore = 0;
        csScoreHistory.length = 0;
        csRoundDetails.length = 0;
        csSentiment = 60;
        chatInput.disabled = true;
        sendBtn.disabled = true;
        chatInput.value = '';
        chatInput.placeholder = '作为客服回复客户...';
        document.getElementById('cs-score-overall').textContent = '-';
        document.getElementById('cs-score-overall').style.color = 'var(--text-muted)';
        ['cs-polite','cs-pro','cs-solve','cs-empathy'].forEach(id => {
            document.getElementById(id).style.width = '0%';
        });
        ['cs-polite-val','cs-pro-val','cs-solve-val','cs-empathy-val'].forEach(id => {
            document.getElementById(id).textContent = '-';
        });
        // 体验优化：清空最弱维度高亮、快捷 chip
        const weakHint = document.getElementById('cs-weak-hint');
        if (weakHint) weakHint.style.display = 'none';
        ['cs-bar-polite','cs-bar-pro','cs-bar-solve','cs-bar-empathy'].forEach(id => {
            document.getElementById(id)?.classList.remove('is-weakest');
        });
        const chips = document.getElementById('cs-quick-chips');
        if (chips) { chips.style.display = 'none'; chips.innerHTML = ''; }
        // 体验优化⑥：重置情绪温度条
        const sentFill = document.getElementById('cs-sentiment-fill');
        const sentLabel = document.getElementById('cs-sentiment-label');
        if (sentFill) { sentFill.style.width = '60%'; sentFill.style.background = '#d9a227'; }
        if (sentLabel) { sentLabel.textContent = '待开始'; sentLabel.style.color = 'var(--text-muted)'; }
        document.getElementById('cs-tips-list').innerHTML = '<div class="cs-tip-item">开始对话后将显示建议</div>';
        document.getElementById('cs-round-count').textContent = '0 轮';
        updateMissionCard();   // 重新渲染任务卡（reset 重建了 DOM）
    });

    // 提示 - AI动态生成
    hintBtn?.addEventListener('click', async () => {
        if (!isStarted) { showNotification('请先开始模拟', 'warning'); return; }

        const scenario = document.getElementById('cs-scenario').value;
        const personality = document.getElementById('cs-personality').value;
        const product = document.getElementById('cs-product').value.trim() || '农产品';
        const tipsList = document.getElementById('cs-tips-list');

        // 获取最后一条客户消息
        const lastCustomerMsg = chatHistory.filter(h => h.role === 'assistant').pop()?.content || '';

        if (tipsList) {
            tipsList.innerHTML = '<div class="cs-tip-item"><i class="fas fa-spinner fa-spin"></i> AI分析中...</div>';
        }

        try {
            const data = await apiCall('/api/ecommerce/customer-service/hint', 'POST', {
                scenario, personality, product, history: chatHistory, last_customer_msg: lastCustomerMsg
            });

            if (data.success && data.hint && tipsList) {
                const h = data.hint;
                tipsList.innerHTML = `
                    ${h.analysis ? `<div class="cs-hint-analysis"><i class="fas fa-search"></i> ${h.analysis}</div>` : ''}
                    ${h.strategy ? `<div class="cs-hint-strategy"><i class="fas fa-chess"></i> 策略：${h.strategy}</div>` : ''}
                    <div class="cs-hint-section">
                        <div class="cs-hint-title">话术参考（点击复制）</div>
                        <div class="cs-hint-templates">
                            ${(h.templates || []).map(t => `<div class="cs-hint-tpl" data-text="${escapeHtml(t)}">${t}</div>`).join('')}
                        </div>
                    </div>
                    ${h.tips && h.tips.length > 0 ? `
                    <div class="cs-hint-section">
                        <div class="cs-hint-title">注意事项</div>
                        ${h.tips.map(t => `<div class="cs-hint-tip-item"><i class="fas fa-info-circle"></i> ${t}</div>`).join('')}
                    </div>` : ''}
                `;
                // P1-1（学员端走查）：hint 接口降级时后端下发 degraded，必须如实标注
                if (data.degraded) {
                    const dnote = document.createElement('div');
                    dnote.className = 'cs-degraded-note';
                    dnote.innerHTML = '<i class="fas fa-exclamation-triangle"></i> 以下为系统内置建议（非 AI 生成）';
                    tipsList.appendChild(dnote);
                }
                // 点击复制话术
                tipsList.querySelectorAll('.cs-hint-tpl').forEach(el => {
                    el.addEventListener('click', () => {
                        copyText(el.dataset.text, '已复制到剪贴板').then(function (ok) {
                            if (!ok) return;
                            el.classList.add('copied');
                            setTimeout(() => el.classList.remove('copied'), 1500);
                        });
                    });
                });

                // 体验优化③（2026-10-06）：把话术模板同步成输入框下方的快捷 chip，
                // 点击直接填入输入框，省去「复制→粘贴」两步。
                const chips = document.getElementById('cs-quick-chips');
                if (chips && h.templates && h.templates.length) {
                    chips.style.display = 'flex';
                    chips.innerHTML = '<span class="cs-quick-chips-label"><i class="fas fa-bolt"></i> 快捷填充</span>' +
                        h.templates.map(t =>
                            `<button class="cs-quick-chip" type="button" data-text="${escapeHtml(t)}">${escapeHtml(t)}</button>`
                        ).join('');
                    chips.querySelectorAll('.cs-quick-chip').forEach(btn => {
                        btn.addEventListener('click', () => {
                            const inp = document.getElementById('cs-input');
                            if (inp) { inp.value = btn.dataset.text; inp.focus(); }
                            showNotification('已填入输入框，可修改后发送', 'success');
                        });
                    });
                }
            }
        } catch(e) {
            // P2-5（2026-10-06 走查）：限流/失败要可见，区分 429 与一般失败。
            if (tipsList) {
                const limited = e && (e.status === 429 || /429/.test(String(e && e.message)));
                tipsList.innerHTML = limited
                    ? '<div class="cs-tip-item"><i class="fas fa-hourglass-half"></i> 建议获取过于频繁，请稍后再试</div>'
                    : '<div class="cs-tip-item"><i class="fas fa-exclamation-circle"></i> 获取建议失败，请重试</div>';
            }
        }
    });

    // 提交实训（客服闭环）：整段对话 + 规则评分落库，kind=cs
    document.getElementById('cs-submit-btn')?.addEventListener('click', async () => {
        if (!isStarted || chatHistory.length === 0) {
            showNotification('请先开始并完成至少一轮对话', 'warning');
            return;
        }
        // P1-1（2026-10-06 走查）：提交分数 = 整场所有已评分轮次的平均分，
        // 而非最后一句。若整场没有成功评分过（异常），用 0 并提示。
        const scored = csScoreHistory.length;
        const overall = scored > 0
            ? Math.round(csScoreHistory.reduce((a, b) => a + b, 0) / scored)
            : 0;
        if (scored === 0) {
            showNotification('本场尚无有效评分，提交后分数暂记 0', 'warning');
        }
        const info = document.getElementById('cs-submit-info');
        try {
            const data = await apiCall('/api/ecommerce/cs/submit', 'POST', {
                product: document.getElementById('cs-product').value.trim() || '农产品',
                transcript: chatHistory,
                score: overall,
                meta: {
                    scenario: document.getElementById('cs-scenario').value,
                    personality: document.getElementById('cs-personality').value,
                    difficulty: document.getElementById('cs-difficulty').value,
                    rounds: Math.floor(chatHistory.length / 2),
                    scored_rounds: scored
                }
            });
            if (data.success) {
                if (info) info.textContent = `已保存实训记录（第 ${data.attempts} 次，整场均分 ${overall}）`;
                showNotification(`已保存实训记录（第 ${data.attempts} 次，整场均分 ${overall}）`, 'success');
                loadTrainingRecords('cs', 'cs-records-body');
                // 体验优化⑤：提交成功后展示整场复盘卡
                renderReviewCard(overall, csRoundDetails);
            }
        } catch (e) {
            // P2（2026-10-06 全局走查）：提交失败要读后端下发的 code 区分原因，
            // 不能让 400 被笼统提示「请稍后重试」掩盖。apiCall 失败时 err.code 直接挂在 error 上。
            const code = e && e.code;
            if (e && e.status === 401) {
                showNotification('保存失败：请先登录', 'warning', { actionLabel: '去登录', action: openLoginModal });
            } else if (code === 'empty_product') {
                showNotification('保存失败：请填写产品名称', 'warning');
            } else if (code === 'empty_transcript') {
                showNotification('保存失败：对话记录为空，请先完成至少一轮对话', 'warning');
            } else if (code === 'rate_limited') {
                showNotification('操作过于频繁，请稍后再试', 'warning');
            } else {
                showNotification('保存失败，请稍后重试', 'error');
            }
        }
    });

    loadTrainingRecords('cs', 'cs-records-body');
}

// 体验优化⑤（2026-10-06）：整场复盘卡——提交后在对话区顶部展示
// 整场均分 + 高光时刻 + 待改进点，让一次训练形成闭环。
function renderReviewCard(overall, roundDetails) {
    const container = document.getElementById('cs-messages');
    if (!container) return;
    // 移除旧的复盘卡
    container.querySelector('.cs-review-card')?.remove();

    const card = document.createElement('div');
    card.className = 'cs-review-card';

    // 高光时刻 = 最高分那一句；待改进 = 最低分那一句
    let best = null, worst = null;
    (roundDetails || []).forEach(r => {
        if (!best || r.score > best.score) best = r;
        if (!worst || r.score < worst.score) worst = r;
    });

    const gradeColor = overall >= 85 ? '#2e7d32' : overall >= 70 ? '#2f6b4f' : overall >= 55 ? '#d9a227' : '#ef4444';
    const gradeLabel = overall >= 85 ? '优秀' : overall >= 70 ? '良好' : overall >= 55 ? '及格' : '待提升';

    card.innerHTML = `
        <div class="cs-review-head">
            <i class="fas fa-flag-checkered"></i>
            <span>训练复盘</span>
        </div>
        <div class="cs-review-overall">
            <div class="cs-review-score" style="color:${gradeColor}">${overall}</div>
            <div class="cs-review-meta">
                <div class="cs-review-grade" style="color:${gradeColor}">${gradeLabel}</div>
                <div class="cs-review-note">整场 ${roundDetails.length} 轮均分</div>
            </div>
        </div>
        ${best ? `
        <div class="cs-review-item cs-review-best">
            <div class="cs-review-item-label"><i class="fas fa-star"></i> 高光时刻（${best.score}分）</div>
            <div class="cs-review-item-text">${escapeHtml(best.text)}</div>
        </div>` : ''}
        ${worst && worst !== best ? `
        <div class="cs-review-item cs-review-worst">
            <div class="cs-review-item-label"><i class="fas fa-arrow-up"></i> 待改进（${worst.score}分）</div>
            <div class="cs-review-item-text">${escapeHtml(worst.text)}</div>
            ${worst.tips && worst.tips.length ? `<div class="cs-review-tip">${escapeHtml(worst.tips[0])}</div>` : ''}
        </div>` : ''}
    `;
    container.insertBefore(card, container.firstChild);
    container.scrollTop = 0;
}

function appendCSMsg(role, text, meta) {
    const container = document.getElementById('cs-messages');
    if (!container) return;
    // 移除欢迎信息
    container.querySelector('.cs-welcome')?.remove();

    const div = document.createElement('div');
    div.className = `cs-msg ${role}`;
    const icon = role === 'customer' ? 'fa-user' : 'fa-headset';
    const label = role === 'customer' ? '客户' : '你（客服）';
    // 体验优化①（2026-10-06）：学员气泡旁标注该句得分（颜色分级）。
    let scoreBadge = '';
    let reasonNote = '';
    if (role === 'agent' && meta && typeof meta.score === 'number') {
        const s = meta.score;
        const grade = s >= 85 ? 'good' : s >= 70 ? 'mid' : s >= 55 ? 'warn' : 'bad';
        scoreBadge = `<span class="cs-msg-score cs-score-${grade}">${s}分</span>`;
        // 扣分原因（取第一条提示，通常是「答非所问」或最要紧的建议）
        if (meta.tips && meta.tips.length) {
            reasonNote = `<div class="cs-msg-reason">${escapeHtml(meta.tips[0])}</div>`;
        }
    }
    div.innerHTML = `
        <div class="cs-msg-avatar"><i class="fas ${icon}"></i></div>
        <div class="cs-msg-content">
            <div class="cs-msg-label">${label} ${scoreBadge}</div>
            <div class="cs-msg-bubble">${escapeHtml(text)}</div>
            ${reasonNote}
        </div>
    `;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
    return div;
}

// P1-3（2026-10-06 走查）：客服回复失败时的可见错误占位（不进入 chatHistory、不冒充客户）。
function appendCSError(text) {
    const container = document.getElementById('cs-messages');
    if (!container) return;
    const div = document.createElement('div');
    div.className = 'cs-msg cs-error-msg';
    div.innerHTML = `
        <div class="cs-msg-avatar"><i class="fas fa-exclamation-triangle"></i></div>
        <div class="cs-msg-content">
            <div class="cs-msg-label">系统提示</div>
            <div class="cs-msg-bubble">${escapeHtml(text)}</div>
        </div>
    `;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
}

function updateCSScore(score) {
    const totalEl = document.getElementById('cs-score-overall');
    if (totalEl) {
        animateNumber(totalEl, score.total, 800);
        const color = score.total >= 85 ? '#1f5e43' : score.total >= 70 ? '#2f6b4f' : score.total >= 55 ? '#d9a227' : '#ef4444';
        totalEl.style.color = color;
    }

    if (score.details) {
        const mapping = [
            { key: 'politeness', fill: 'cs-polite', val: 'cs-polite-val', bar: 'cs-bar-polite', label: '礼貌度' },
            { key: 'professional', fill: 'cs-pro', val: 'cs-pro-val', bar: 'cs-bar-pro', label: '专业度' },
            { key: 'solving', fill: 'cs-solve', val: 'cs-solve-val', bar: 'cs-bar-solve', label: '解决力' },
            { key: 'empathy', fill: 'cs-empathy', val: 'cs-empathy-val', bar: 'cs-bar-empathy', label: '同理心' }
        ];
        mapping.forEach((m, i) => {
            const v = score.details[m.key] || 0;
            setTimeout(() => {
                const fill = document.getElementById(m.fill);
                const val = document.getElementById(m.val);
                if (fill) { fill.style.transition = 'width 0.6s ease'; fill.style.width = v + '%'; }
                if (val) val.textContent = v;
            }, i * 100);
        });

        // 体验优化②（2026-10-06）：高亮最弱维度 + 一句可行动建议
        let weakest = null;
        mapping.forEach(m => {
            const v = score.details[m.key] || 0;
            const bar = document.getElementById(m.bar);
            if (bar) bar.classList.remove('is-weakest');
            if (!weakest || v < weakest.v) weakest = { v, m };
        });
        const weakHint = document.getElementById('cs-weak-hint');
        if (weakest && weakest.m && weakHint) {
            const bar = document.getElementById(weakest.m.bar);
            if (bar) bar.classList.add('is-weakest');
            // 各维度的可行动建议映射
            const advices = {
                politeness: '试试用「亲 / 您好」开头，语气更亲切',
                professional: '补上产地、品种、规格等信息更有说服力',
                solving: '明确告诉客户解决方案，如「帮您补发」',
                empathy: '先说「理解您的心情」，再给方案效果更好'
            };
            const advice = advices[weakest.m.key] || '';
            if (advice && weakest.v < 85) {
                weakHint.style.display = 'block';
                weakHint.innerHTML = '<i class="fas fa-bullseye"></i><span>最弱：<b>' + weakest.m.label +
                    '</b>（' + weakest.v + '）· ' + escapeHtml(advice) + '</span>';
            } else {
                weakHint.style.display = 'none';
            }
        }
    }

    if (score.tips && score.tips.length > 0) {
        const tipsList = document.getElementById('cs-tips-list');
        if (tipsList) {
            tipsList.innerHTML = score.tips.map(t =>
                `<div class="cs-tip-item"><i class="fas fa-check-circle"></i> ${t}</div>`
            ).join('');
        }
    }
}

// 体验优化⑥（2026-10-06）：更新客户情绪温度条。
// sentiment = { level: 0-100, label: '满意'|'较满意'|'一般'|'不满' }
function updateCSSentiment(sentiment) {
    const fill = document.getElementById('cs-sentiment-fill');
    const label = document.getElementById('cs-sentiment-label');
    if (!fill || !label || !sentiment) return;
    const lv = sentiment.level;
    const color = lv >= 70 ? '#2e7d32' : lv >= 52 ? '#d9a227' : '#ef4444';
    fill.style.transition = 'width 0.8s ease, background 0.5s ease';
    fill.style.width = lv + '%';
    fill.style.background = color;
    label.textContent = sentiment.label || '一般';
    label.style.color = color;
}

function appendChatMsg(role, text) {
    const container = document.getElementById('chat-messages');
    if (!container) return;
    const div = document.createElement('div');
    div.className = `chat-msg ${role}`;
    div.innerHTML = `<div class="msg-content">${text}</div>`;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
}

// ==================== 成功案例按钮 ====================
// 案例详情已改为 <a> 链接跳转到 case-detail.html，无需JS绑定

function setupCaseButtons() {
    // 案例卡片已使用超链接跳转到独立详情页
}

// ==================== 政策信息 ====================
// 内容唯一事实源 = 后端 policies_data.py（经 /api/resources/policies 下发）。
// 卡片动态渲染；正文 + 资料来源 + 免责声明均来自同一份接口数据，避免与后端双份维护。
let _policiesLoaded = false;
let _policyList = [];
let _policyNotes = { source_note: '', disclaimer: '' };

// 分类 → 卡片图标/标签色（仅展示用；未知分类走中性默认，不因缺映射而不渲染）
const POLICY_CATEGORY_STYLE = {
    '补贴': { icon: 'fa-hand-holding-usd', tag: 'tag-subsidy' },
    '电商': { icon: 'fa-shopping-cart',    tag: 'tag-ecommerce' },
    '非遗': { icon: 'fa-university',       tag: 'tag-heritage' },
    '培训': { icon: 'fa-graduation-cap',   tag: 'tag-training' },
    '认证': { icon: 'fa-certificate',      tag: 'tag-cert' },
    '综合': { icon: 'fa-file-alt',         tag: 'tag-general' }
};

// ⚠️ 未知分类的默认样式必须是**中性**的。
//    原实现回退成 tag-subsidy（补贴绿）→ 学员会把一条非补贴政策看成补贴政策。
const POLICY_CATEGORY_FALLBACK = { icon: 'fa-file-alt', tag: 'tag-general' };

// 已知分类的展示顺序（数据里真实出现的分类按此排序，其它分类按出现顺序追加在后）
const POLICY_CATEGORY_ORDER = ['补贴', '电商', '非遗', '培训', '认证', '综合'];

// 筛选按钮按数据里**真实出现的分类**动态生成。
// ⚠️ 原来写死了 5 个分类按钮，而政府端可以发布这 5 类之外的政策（表单里就有「综合」）。
//    那条政策于是永远筛不到，界面上却没有任何提示 —— 学员会觉得这条政策凭空消失了。
function renderPolicyFilters(policies) {
    const box = document.querySelector('.policy-filters');
    if (!box) return;

    const present = [];
    policies.forEach(p => {
        const c = p.category || '综合';
        if (present.indexOf(c) === -1) present.push(c);
    });
    present.sort((a, b) => {
        const ia = POLICY_CATEGORY_ORDER.indexOf(a), ib = POLICY_CATEGORY_ORDER.indexOf(b);
        return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib);
    });

    const activeBtn = box.querySelector('.policy-filter.active');
    const keep = (activeBtn && activeBtn.dataset.filter) || 'all';
    const items = [{ k: 'all', label: '全部' }].concat(present.map(c => ({ k: c, label: c })));
    // 之前选中的分类若在新数据里已不存在，退回「全部」，避免出现「高亮了但一条都没有」
    const keepOk = keep === 'all' || present.indexOf(keep) !== -1;

    box.innerHTML = items.map(x =>
        `<button class="policy-filter${(keepOk && x.k === keep) ? ' active' : ''}" data-filter="${attrEsc(x.k)}">${escapeHtml(x.label)}</button>`
    ).join('');
    if (!box.querySelector('.policy-filter.active')) {
        box.querySelector('.policy-filter').classList.add('active');
    }
}

function setupPolicySection() {
    // 分类筛选：绑在**容器**上用事件委托。
    // 按钮是异步按数据重建的（renderPolicyFilters 会重写 innerHTML），
    // 初始化时 querySelectorAll 绑的监听会随着重建一起丢失。
    const filters = document.querySelector('.policy-filters');
    if (filters) {
        filters.addEventListener('click', function(e) {
            const btn = e.target.closest('.policy-filter');
            if (!btn) return;
            filters.querySelectorAll('.policy-filter').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            applyPolicyFilter(btn.dataset.filter);
        });
    }

    // 政策卡片点击 → 弹窗。
    // 卡片是异步渲染的，必须用事件委托，不能在初始化时 querySelectorAll 一次性绑定。
    const grid = document.getElementById('policy-grid');
    if (grid) {
        grid.addEventListener('click', function(e) {
            const card = e.target.closest('.policy-card');
            if (!card) return;
            const policy = _policyList[Number(card.dataset.index)];
            if (policy) {
                showPolicyModal(policy);
            } else {
                showNotification('未找到该政策详情', 'warning');
            }
        });
    }
}

// 「一条政策都没有」是**合法结果**（政府端尚未发布，或政策已全部下架），
// 必须与「加载失败」区分开：
//   原实现把空列表 throw 成错误态 → 学员看到「政策加载失败：暂无政策数据」+ 重试按钮，
//   会理解成平台故障；而政府端把政策**全部下架**时必然触发，等于把一次正常的下架操作
//   呈现成了一次故障（配合后端降级 bug 更是双重误判）。
function renderPoliciesEmpty(message) {
    const grid = document.getElementById('policy-grid');
    if (!grid) return;
    grid.innerHTML = `<div class="policies-empty">
        <i class="fas fa-folder-open"></i>
        <p>${escapeHtml(message)}</p>
        <p class="policies-empty-sub">政策由各地农业农村主管部门发布；未发布或已下架时此处为空。</p>
        <button class="btn btn-outline btn-sm" onclick="loadPolicies(true)"><i class="fas fa-redo"></i> 刷新</button>
    </div>`;
}

function applyPolicyFilter(filter) {
    let visible = 0;
    document.querySelectorAll('#policy-grid .policy-card').forEach(card => {
        const hit = filter === 'all' || card.dataset.category === filter;
        card.style.display = hit ? '' : 'none';
        if (hit) visible++;
    });

    // 该分类下一条都没有 → 必须给提示。
    // 原来只是把卡片全部 display:none，学员看到的是一片空白，会以为页面坏了。
    // 触发场景很常见：政府端下架了某分类下唯一的一条政策。
    const grid = document.getElementById('policy-grid');
    if (!grid) return;
    if (visible === 0) {
        renderPoliciesEmpty(filter === 'all'
            ? '暂时没有可显示的政策'
            : `「${filter}」分类下暂时没有政策`);
        return;
    }
    const old = grid.querySelector('.policies-empty');
    if (old) old.remove();
}

async function loadPolicies(force) {
    const grid = document.getElementById('policy-grid');
    if (!grid) return;
    if (_policiesLoaded && !force) return;

    grid.innerHTML = '<div class="policy-placeholder"><i class="fas fa-spinner fa-spin"></i> 正在加载政策…</div>';

    try {
        const res = await fetch('/api/resources/policies');
        if (!res.ok) throw new Error('HTTP ' + res.status);
        const data = await res.json();
        if (!data.success || !Array.isArray(data.policies)) {
            throw new Error(data.message || '返回数据格式异常');
        }
        if (data.policies.length === 0) {
            // 空列表是合法结果（未发布/已全部下架），不是失败 —— 走空态，不走错误态。
            _policyList = [];
            _policyNotes = {
                source_note: data.source_note || '',
                disclaimer: data.disclaimer || ''
            };
            renderPolicyFilters([]);
            renderPoliciesEmpty('暂时没有可显示的政策');
            _policiesLoaded = true;
            return;
        }
        _policyList = data.policies;
        _policyNotes = {
            source_note: data.source_note || '',
            disclaimer: data.disclaimer || ''
        };
        renderPolicies(data.policies);
        // 先按「数据里真实出现的分类」重建筛选按钮，再按当前选中项过滤。
        // （renderPolicyFilters 会把已消失的分类退回「全部」，所以要在它之后再取 active）
        renderPolicyFilters(data.policies);
        const active = document.querySelector('.policy-filter.active');
        applyPolicyFilter(active ? active.dataset.filter : 'all');
        _policiesLoaded = true;
    } catch (e) {
        console.error('加载政策失败:', e);
        grid.innerHTML = `
            <div class="policies-error">
                <i class="fas fa-exclamation-circle"></i>
                <p>政策加载失败：${escapeHtml(e.message || '未知错误')}</p>
                <button class="btn btn-outline btn-sm" onclick="loadPolicies(true)">
                    <i class="fas fa-redo"></i> 重试
                </button>
            </div>`;
    }
}

function renderPolicies(policies) {
    const grid = document.getElementById('policy-grid');
    if (!grid) return;
    grid.innerHTML = policies.map((p, i) => {
        // 分类由后端归一化（general → 综合，见 database.normalize_policy_category），
        // 前端不假设一定是已知分类：未知分类走中性默认样式，绝不冒充成「补贴」。
        const cat = p.category || '综合';
        const style = POLICY_CATEGORY_STYLE[cat] || POLICY_CATEGORY_FALLBACK;
        // escapeHtml 不转引号，进属性前补一道（分类可能来自政府端输入）
        const catAttr = attrEsc(cat);
        // 摘要缺失时整行不渲染（不用"暂无"类占位充数）
        const summaryHtml = p.summary ? `<p>${escapeHtml(p.summary)}</p>` : '';
        return `
        <div class="policy-card" data-category="${catAttr}" data-index="${i}">
            <div class="policy-card-top">
                <div class="policy-icon-lg"><i class="fas ${style.icon}"></i></div>
                <span class="policy-tag ${style.tag}">${escapeHtml(cat)}</span>
            </div>
            <h4>${escapeHtml(p.title || '')}</h4>
            ${summaryHtml}
            <div class="policy-card-footer">
                ${p.date ? `<span class="policy-date"><i class="far fa-calendar-alt"></i> ${escapeHtml(p.date)}</span>` : '<span class="policy-date"></span>'}
                <span class="policy-detail-btn">查看详情 <i class="fas fa-arrow-right"></i></span>
            </div>
        </div>`;
    }).join('');
}

function showPolicyModal(policy) {
    const html = formatPolicyContent(policy.content);

    // 资料来源（后端 sources 字段；没有就整块不渲染）
    const sources = Array.isArray(policy.sources) ? policy.sources : [];
    let srcHtml = '';
    if (sources.length) {
        srcHtml = `<div class="policy-sources">
            <h4><i class="fas fa-book"></i> 资料来源</h4>
            <ul>${sources.map(s => {
                const meta = [s.media, s.date].filter(Boolean).join(' · ');
                const label = escapeHtml(s.title || s.media || s.url || '');
                const url = safePolicyUrl(s.url);
                const link = url
                    ? `<a href="${url}" target="_blank" rel="noopener noreferrer">${label}</a>`
                    : label;
                return `<li>${link}${meta ? `<span class="src-meta">${escapeHtml(meta)}</span>` : ''}</li>`;
            }).join('')}</ul>
        </div>`;
    }

    // 口径说明 + 免责声明（后端 policy_notes 下发；都缺失则整块不渲染）
    // ⚠️ source_note（"本页依据公开政策文件整理，文号与数据均可溯源"）是对**来源区块**的背书，
    //    只有这条政策确实带了 sources 才成立。政府端自建政策没有来源，
    //    原实现无条件挂上这句 → 等于替一条无出处的政策做了「可溯源」承诺（口径失真）。
    //    故：无 sources 时只保留免责声明（免责声明对任何政策都成立）。
    const notes = (sources.length ? [_policyNotes.source_note] : [])
        .concat([_policyNotes.disclaimer]).filter(Boolean);
    const noteHtml = notes.length
        ? `<div class="policy-disclaimer"><i class="fas fa-info-circle"></i> <span>${notes.map(escapeHtml).join('<br>')}</span></div>`
        : '';

    showDetailModal(policy.title, `<div class="policy-detail-content">${html}${srcHtml}${noteHtml}</div>`);
}

function formatPolicyContent(text) {
    if (!text) return '<p>暂无详细内容</p>';
    const lines = text.split('\n');
    let html = '';
    let inList = false;
    let listType = 'ul';

    for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) {
            if (inList) {
                html += `</${listType}>`;
                inList = false;
            }
            continue;
        }

        // 标题行：【xxx】
        if (trimmed.startsWith('【') && trimmed.endsWith('】')) {
            if (inList) { html += `</${listType}>`; inList = false; }
            html += `<h4>${policyInline(trimmed.slice(1, -1))}</h4>`;
            continue;
        }

        // 无序列表：• 开头
        if (trimmed.startsWith('•') || trimmed.startsWith('-')) {
            if (!inList) { html += '<ul>'; inList = true; listType = 'ul'; }
            html += `<li>${policyInline(trimmed.slice(1).trim())}</li>`;
            continue;
        }

        // 有序列表：数字. 开头
        if (/^\d+\./.test(trimmed)) {
            if (!inList || listType !== 'ol') {
                if (inList) html += `</${listType}>`;
                html += '<ol>';
                inList = true;
                listType = 'ol';
            }
            html += `<li>${policyInline(trimmed.replace(/^\d+\.\s*/, ''))}</li>`;
            continue;
        }

        // 普通段落
        if (inList) { html += `</${listType}>`; inList = false; }
        html += `<p>${policyInline(trimmed)}</p>`;
    }

    if (inList) html += `</${listType}>`;
    return html;
}

// 政策正文行内格式：先做 HTML 转义（正文可能来自政府端用户输入），
// 再把 **粗体** 转成 <strong>（预置内容只用这一种行内标记）。
function policyInline(s) {
    return escapeHtml(s).replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
}

// 政策来源链接：只放行 http(s)，并额外转义引号（escapeHtml 走 textContent 不转引号，
// 直接拼进 href="..." 不安全）。返回空串表示不可用，调用方退化为纯文本。
function safePolicyUrl(u) {
    const s = String(u == null ? '' : u).trim();
    if (!/^https?:\/\//i.test(s)) return '';
    return escapeHtml(s).replace(/["']/g, m => (m === '"' ? '%22' : '%27')).replace(/\s/g, '');
}

// ==================== 就业模块 ====================

function setupEmploymentTab() {
    setupEmploymentSubTabs();
    setupEmploymentSearch();
    setupApplicationStatusTabs();
    setupResumePanel();
    // 初始加载职位列表（不需要登录）
    loadJobListings();
}

function setupEmploymentSubTabs() {
    document.querySelectorAll('.emp-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            const target = tab.dataset.empTab;
            document.querySelectorAll('.emp-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            document.querySelectorAll('.emp-panel').forEach(p => p.classList.remove('active'));
            const panel = document.getElementById(`emp-${target}-panel`);
            if (panel) panel.classList.add('active');
            // 切换时加载对应数据
            if (target === 'applications') loadMyJobs();
            if (target === 'saved') loadSavedJobs();
            if (target === 'resume') loadResumePanel();
        });
    });
}

function setupEmploymentSearch() {
    const btn = document.getElementById('emp-search-btn');
    if (!btn) return;
    btn.addEventListener('click', () => loadJobListings());
    // 回车搜索
    const input = document.getElementById('emp-keyword');
    if (input) input.addEventListener('keydown', e => { if (e.key === 'Enter') loadJobListings(); });
}

function setupApplicationStatusTabs() {
    document.querySelectorAll('.emp-app-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.emp-app-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            loadMyJobs(tab.dataset.status);
        });
    });
}

async function loadEmploymentData() {
    // 职位列表不需要登录即可加载
    await loadJobListings();
}

async function loadJobListings(filters) {
    const listEl = document.getElementById('emp-job-list');
    const emptyEl = document.getElementById('emp-jobs-empty');
    const totalEl = document.getElementById('emp-job-total');
    if (!listEl) return;

    // 收集筛选条件
    if (!filters) {
        filters = {
            keyword: document.getElementById('emp-keyword')?.value || '',
            location: document.getElementById('emp-location-filter')?.value || '',
            salary: document.getElementById('emp-salary-filter')?.value || '',
            category: document.getElementById('emp-category-filter')?.value || ''
        };
    }

    const params = new URLSearchParams();
    if (filters.keyword) params.set('keyword', filters.keyword);
    if (filters.location) params.set('location', filters.location);
    if (filters.salary) params.set('salary', filters.salary);
    if (filters.category) params.set('category', filters.category);

    try {
        showSkeleton(listEl, 'card', 3);
        const data = await apiCall(`/api/employment/jobs?${params.toString()}`);
        if (data.success) {
            const jobs = data.jobs || [];
            // 公开招聘（公告）：带薪资筛选时不展示 —— 公告没有薪资字段，
            // 让它出现在「薪资 5000-8000」的筛选结果里属于误导。
            // ⚠️ 但「隐了」必须说出来：旧版只把两类都清空、只留一句「未找到匹配的职位」，
            // 学员选一次薪资就以为岗位全没了（2026-10-07 实测整页 0 条）。见 renderFilterNote。
            const recs = (!filters.salary && data.recruitments) ? data.recruitments : [];
            const total = jobs.length + recs.length;

            // 分类下拉按真实条数重建（0 条的标「暂无」）+ 条数构成 + 筛选范围说明 + 空态原因
            renderCategoryFilter(data.category_options, filters.category);
            renderJobCount(totalEl, document.getElementById('emp-job-breakdown'), jobs.length, recs.length);
            renderFilterNote(document.getElementById('emp-filter-note'), filters, data);
            renderReviewPending(jobs.length, data);

            if (total === 0) {
                listEl.innerHTML = '';
                if (emptyEl) emptyEl.style.display = 'block';
                renderEmptyReason(document.getElementById('emp-jobs-empty-title'),
                                  document.getElementById('emp-jobs-empty-hint'),
                                  filters, data);
            } else {
                if (emptyEl) emptyEl.style.display = 'none';
                // 获取收藏状态（只有企业岗位可收藏；公告是外链，不进收藏表）
                let savedIds = [];
                if (AppState.user) {
                    try {
                        const savedData = await apiCall(`/api/employment/saved/${AppState.user.id}`);
                        if (savedData.success) savedIds = savedData.saved_ids;
                    } catch(e) { console.warn('[就业对接] 收藏状态加载失败', e); }
                }
                // 公告详情直接从列表数据渲染（后端已下发全字段，点开不必再请求）
                RECRUIT_CACHE = {};
                recs.forEach(r => { RECRUIT_CACHE[r.key] = r; });
                RECRUIT_NOTES = {
                    sourceNote: data.recruit_source_note || '',
                    disclaimer: data.recruit_disclaimer || ''
                };

                // 招聘公告的报名是有期限的，过期即失效 ——
                // 可报名的（报名中 / 即将开始）正常展示；已过报名期的默认折叠，
                // 需要时展开仍能看岗位条件，但不会让首屏看起来"全是不能报的"。
                const activeRecs = recs.filter(r => r.status === 'open' || r.status === 'upcoming');
                const expiredRecs = recs.filter(r => r.status !== 'open' && r.status !== 'upcoming');

                let html = '';
                if (activeRecs.length) {
                    html += `<div class="emp-list-section-title"><i class="fas fa-bullhorn"></i>公开招聘信息` +
                            `<span class="emp-list-section-note">官方公告汇编 · 点卡片查看公告原文</span></div>`;
                    html += activeRecs.map(renderRecruitCard).join('');
                }
                if (expiredRecs.length) {
                    html += `<details class="emp-recruit-expired"><summary>` +
                            `<i class="fas fa-clock-rotate-left"></i>已过报名期 ${expiredRecs.length} 条` +
                            `<span class="emp-recruit-expired-note">报名已结束，仅作岗位与条件参考</span>` +
                            `</summary>` + expiredRecs.map(renderRecruitCard).join('') +
                            `</details>`;
                }
                if (jobs.length) {
                    if (recs.length) {
                        html += `<div class="emp-list-section-title"><i class="fas fa-building"></i>企业招聘岗位` +
                                `<span class="emp-list-section-note">由入驻企业发布，平台审核通过后展示</span></div>`;
                    }
                    html += jobs.map(job => renderJobCard(job, savedIds)).join('');
                }
                listEl.innerHTML = html;
                bindJobCardEvents(listEl);
            }
            if (totalEl) totalEl.textContent = total;   // 与 renderJobCount 同值，见上

            // 公开招聘的口径说明（有公告才展示）—— 文案出自后端 jobs_data.py，前端不硬编码
            const footEl = document.getElementById('emp-recruit-footnote');
            if (footEl) {
                if (recs.length) {
                    footEl.style.display = 'block';
                    footEl.innerHTML = '<i class="fas fa-info-circle"></i> ' +
                        escapeHtml(RECRUIT_NOTES.sourceNote || '') +
                        (RECRUIT_NOTES.disclaimer ? '<br>' + escapeHtml(RECRUIT_NOTES.disclaimer) : '');
                } else {
                    footEl.style.display = 'none';
                    footEl.innerHTML = '';
                }
            }
        }
    } catch(e) {
        showErrorState(listEl, '加载职位失败', () => loadJobListings(filters));
    }
}

/* ==================== 筛选反馈（条数构成 / 生效范围 / 空态原因 / 分类下拉）====================
   2026-10-07 学员视角走查：旧版筛选一旦筛空，界面只剩一句「未找到匹配的职位」，
   学员无从判断是「平台没有这类岗位」「我选错了」还是「筛选把别的内容藏起来了」。
   下面四个小函数把这四件事分别说清楚。全部对字段缺失兜底（新前端 + 旧后端是常态）。 */

// 分类下拉：老后端没下发 category_options 时保持 index.html 的静态项，不重建
const CATEGORY_STATIC_FALLBACK = {
    enterprise: ['农业技术', '电商运营', '手工工艺', '乡村旅游', '物流仓储'],
    recruit: ['基层服务', '乡村治理']
};

function renderCategoryFilter(opts, keep) {
    const sel = document.getElementById('emp-category-filter');
    if (!sel || !opts || (!opts.enterprise && !opts.recruit)) return;
    const groups = {
        enterprise: (opts.enterprise || []).slice(),
        recruit: (opts.recruit || []).slice()
    };
    // 当前选中项若在当前条件下 0 条（因而不在 options 里）也要留住，
    // 否则 select 会静默跳回「职位类型」，和列表状态对不上，更让人困惑。
    if (keep) {
        const inEnt = CATEGORY_STATIC_FALLBACK.enterprise.indexOf(keep) !== -1;
        const inRec = CATEGORY_STATIC_FALLBACK.recruit.indexOf(keep) !== -1;
        const g = (inRec && !inEnt) ? 'recruit' : 'enterprise';
        if (!groups[g].some(o => o.value === keep)) groups[g].push({ value: keep, count: 0 });
    }
    const build = (label, list) => {
        if (!list || !list.length) return '';
        const items = list.map(o => {
            const n = (o.count > 0) ? o.count : '暂无';
            return `<option value="${escapeHtml(o.value)}">${escapeHtml(o.value)}（${n}）</option>`;
        }).join('');
        return `<optgroup label="${escapeHtml(label)}">${items}</optgroup>`;
    };
    sel.innerHTML = '<option value="">职位类型</option>' +
        build('企业招聘岗位', groups.enterprise) + build('公开招聘公告', groups.recruit);
    sel.value = [].some.call(sel.options, o => o.value === keep) ? keep : '';
}

// 「共 N 条信息（企业岗位 x · 公开招聘 y）」—— 两类混算时数字本身没有含义
function renderJobCount(totalEl, breakdownEl, entCount, recCount) {
    if (totalEl) totalEl.textContent = entCount + recCount;
    if (breakdownEl) {
        breakdownEl.textContent = (entCount + recCount > 0)
            ? `（企业岗位 ${entCount} · 公开招聘 ${recCount}）` : '';
    }
}

// 企业岗位要经管理员审核通过才展示（后端只下发 review_status='approved'）。
// 岗位全在审时列表里一条企业岗都没有 —— 必须说出来，
// 否则学员会以为平台没有企业岗位，或者以为筛选坏了。
function renderReviewPending(shownCount, data) {
    const el = document.getElementById('emp-review-pending');
    if (!el) return;
    const pending = parseInt(data.enterprise_review_pending, 10) || 0;
    if (pending > 0 && shownCount === 0) {
        el.style.display = 'flex';
        el.innerHTML = '<i class="fas fa-hourglass-half"></i>' +
            `<span>另有 <b>${pending}</b> 条企业发布的岗位<b>正在审核中</b>，` +
            '通过平台审核后才会在这里展示。</span>';
    } else {
        el.style.display = 'none';
        el.innerHTML = '';
    }
}

// 筛选生效范围的说明：薪资只作用于企业岗位 → 公告被隐藏这件事必须讲出来
function renderFilterNote(noteEl, filters, data) {
    if (!noteEl) return;
    const hidden = parseInt(data.recruit_hidden_by_salary, 10) || 0;
    if (filters.salary && hidden > 0) {
        noteEl.style.display = 'block';
        noteEl.innerHTML = '<i class="fas fa-circle-info"></i> 薪资筛选只作用于<b>企业招聘岗位</b>：' +
            `${hidden} 条公开招聘公告没有薪资字段、不参与薪资筛选，已暂时隐藏。` +
            '想同时看公告，把「薪资范围」清空即可。';
    } else {
        noteEl.style.display = 'none';
        noteEl.innerHTML = '';
    }
}

// 空态原因：按「哪个筛选条件把结果筛没了」给不同解释，而不是统一一句「未找到」
function renderEmptyReason(titleEl, hintEl, filters, data) {
    const cat = (filters.category || '').trim();
    // 企业岗位要过审才露出（见后端 review_status='approved'），全在待审时这里就是 0 条
    const pending = parseInt(data.enterprise_review_pending, 10) || 0;
    let title = '未找到匹配的职位';
    let hint = '';
    if (cat && findCategoryCount(data.category_options, cat) === 0) {
        title = `「${cat}」下暂时没有岗位`;
        hint = '分类下拉里已标出每一类的真实条数（没有内容的标「暂无」），可以换一个分类看看。';
    } else if (cat) {
        title = `「${cat}」在当前搜索 / 地点条件下没有岗位`;
        hint = '试试清空搜索关键词，或把工作地点改回「工作地点」（不限）。';
    } else if (filters.salary) {
        title = '没有薪资落在这个范围内的企业岗位';
        hint = '公开招聘公告没有薪资字段、不参与薪资筛选；把「薪资范围」清空即可看到全部公告。';
    } else if (filters.keyword || filters.location) {
        hint = '试试减少搜索关键词，或把工作地点改回不限。';
    }
    // 什么筛选都没设却一条都没有：多半是企业岗位全卡在审核里（学员端只看已通过的）。
    // 不说清楚的话，学员会以为平台根本没有企业岗位。
    if (pending > 0 && !cat && !filters.salary && !filters.keyword && !filters.location) {
        title = '企业岗位正在审核中';
        hint = `有 ${pending} 条企业发布的岗位尚未通过平台审核，通过后才会在这里展示。`;
    }
    if (titleEl) titleEl.textContent = title;
    if (hintEl) hintEl.textContent = hint;
}

function findCategoryCount(opts, value) {
    if (!opts || !value) return -1;
    const all = [].concat(opts.enterprise || [], opts.recruit || []);
    const hit = all.filter(o => o.value === value)[0];
    return hit ? hit.count : -1;
}

function renderJobCard(job, savedIds = []) {
    const initial = getCompanyInitial(job.company);
    const dateStr = computeRelativeDate(job.posted_at);
    const isSaved = savedIds.includes(job.id);
    const tags = (job.requirements || []).slice(0, 3);
    if (job.category) tags.unshift(job.category);
    // 演示岗位（is_demo=1）必须打角标 —— 公司名也已带「（演示）」后缀，双重标注防误认
    const demoTxt = job.is_demo
        ? '<span class="emp-tag emp-tag-demo"><i class="fas fa-flask"></i>演示数据</span>' : '';

    return `
    <div class="emp-job-card ${job.is_demo ? 'is-demo' : ''}" data-job-id="${job.id}">
        <div class="emp-job-card-left">
            <div class="emp-company-logo">${escapeHtml(initial)}</div>
        </div>
        <div class="emp-job-card-body">
            <div class="emp-job-header">
                <span class="emp-job-title">${escapeHtml(job.title)}</span>
                <span class="emp-job-salary">${escapeHtml(job.salary)}</span>
            </div>
            <div class="emp-job-company">
                ${escapeHtml(job.company)}<span class="emp-dot">·</span>${escapeHtml(job.location || '广东')}<span class="emp-dot">·</span>${escapeHtml(job.experience || '不限')}<span class="emp-dot">·</span>${escapeHtml(job.education || '不限')}
            </div>
            <div class="emp-job-tags">
                ${demoTxt}<span class="emp-tag emp-tag-src"><i class="fas fa-building"></i>企业发布</span>
                ${tags.map(t => `<span class="emp-tag">${escapeHtml(t)}</span>`).join('')}
            </div>
        </div>
        <div class="emp-job-card-right">
            <span class="emp-job-date">${escapeHtml(dateStr)}</span>
            <button class="btn btn-primary btn-sm emp-apply-btn" data-job-id="${job.id}">申请职位</button>
            <button class="emp-save-btn ${isSaved ? 'saved' : ''}" data-job-id="${job.id}" title="${isSaved ? '取消收藏' : '收藏'}">
                <i class="${isSaved ? 'fas' : 'far'} fa-heart"></i>
            </button>
        </div>
    </div>`;
}

/* ============ 公开招聘（招募）公告卡片 ============
   公告来自 jobs_data.py（策展内容，带官方来源），与「企业岗位」是两回事：
     · 不做站内申请（去发布单位官方系统报名），按钮是「查看公告」外链；
     · 不进收藏表（收藏只针对企业岗位）；
     · 有报名截止期，过期如实标注，不以"在招"迷惑学员。
   状态色：报名中=绿、即将开始=蓝、已过期=灰。 */
let RECRUIT_CACHE = {};
// 后端下发口径说明（source_note / disclaimer 都出自 jobs_data.py，不在前端硬编码）
let RECRUIT_NOTES = {};

const RECRUIT_STATUS_CLS = { open: 'rec-open', upcoming: 'rec-upcoming', closed: 'rec-closed', unknown: 'rec-unknown' };

function renderRecruitCard(r) {
    const cls = RECRUIT_STATUS_CLS[r.status] || 'rec-unknown';
    const chips = [];
    if (r.category) chips.push(r.category);
    if (r.headcount) chips.push(r.headcount);
    if (r.education) chips.push(r.education);
    const deadlineTxt = r.deadline ? ('报名截止 ' + r.deadline) : '';
    let leftTxt = '';
    if (r.status === 'open' && r.days_left != null) leftTxt = `还剩 ${r.days_left} 天`;
    else if (r.status === 'upcoming' && r.starts_in != null) leftTxt = `距开始报名 ${r.starts_in} 天`;
    return `
    <div class="emp-job-card emp-recruit-card ${r.status === 'closed' ? 'is-closed' : ''}" data-recruit-key="${attrEsc(r.key)}">
        <div class="emp-job-card-left">
            <div class="emp-company-logo emp-recruit-logo"><i class="fas fa-bullhorn"></i></div>
        </div>
        <div class="emp-job-card-body">
            <div class="emp-job-header">
                <span class="emp-job-title">${escapeHtml(r.title)}</span>
                <span class="emp-recruit-status ${cls}">${escapeHtml(r.status_label)}</span>
            </div>
            <div class="emp-job-company">
                ${escapeHtml(r.org || '')}${r.region ? '<span class="emp-dot">·</span>' + escapeHtml(r.region) : ''}${r.job_type ? '<span class="emp-dot">·</span>' + escapeHtml(r.job_type) : ''}
            </div>
            <div class="emp-job-tags">
                <span class="emp-tag emp-tag-src emp-tag-rec"><i class="fas fa-bullhorn"></i>公开招聘</span>
                ${chips.map(t => `<span class="emp-tag">${escapeHtml(t)}</span>`).join('')}
            </div>
        </div>
        <div class="emp-job-card-right">
            ${deadlineTxt ? `<span class="emp-job-date">${escapeHtml(deadlineTxt)}</span>` : ''}
            ${leftTxt ? `<span class="emp-recruit-left">${escapeHtml(leftTxt)}</span>` : ''}
            <button class="btn btn-outline btn-sm emp-recruit-btn" data-recruit-key="${attrEsc(r.key)}"><i class="fas fa-external-link-alt"></i> 查看公告</button>
        </div>
    </div>`;
}

function bindJobCardEvents(container) {
    // 公开招聘公告卡片：点卡片任意处 → 公告详情（无申请/收藏）
    container.querySelectorAll('.emp-recruit-card').forEach(card => {
        card.addEventListener('click', () => openRecruitDetail(card.dataset.recruitKey));
    });
    // 企业岗位卡片点击 → 职位详情（:not 排除公告卡，避免重复绑定）
    container.querySelectorAll('.emp-job-card:not(.emp-recruit-card)').forEach(card => {
        card.addEventListener('click', (e) => {
            if (e.target.closest('.emp-apply-btn') || e.target.closest('.emp-save-btn')) return;
            const jobId = card.dataset.jobId;
            openJobDetail(jobId);
        });
    });
    // 申请按钮
    container.querySelectorAll('.emp-apply-btn').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            e.stopPropagation();
            await applyForJob(btn.dataset.jobId);
        });
    });
    // 收藏按钮
    container.querySelectorAll('.emp-save-btn').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            e.stopPropagation();
            await toggleSaveJob(btn.dataset.jobId, btn);
        });
    });
}

async function openJobDetail(jobId) {
    try {
        const [jobData, similarData] = await Promise.all([
            apiCall(`/api/employment/jobs/${jobId}`),
            apiCall(`/api/employment/jobs/${jobId}/similar`)
        ]);
        if (!jobData.success) return;
        const job = jobData.job;
        const similar = similarData.success ? similarData.jobs : [];
        const initial = getCompanyInitial(job.company);
        const reqsList = (job.requirements || []).map(r => `<li>${r}</li>`).join('');
        const dateStr = computeRelativeDate(job.posted_at);

        // 演示岗位必须在详情页顶部说清楚，避免学员当成真实在招岗位去投递。
        // 2026-10-07：它们已改为「演示企业账号发布 + 管理员审核通过」的真实链路产物，
        // 说明里据实写清，别让学员以为这是平台凭空塞的数据。
        const demoNotice = job.is_demo
            ? '<div class="emp-demo-notice"><i class="fas fa-flask"></i>' +
              '<div><strong>这是演示岗位</strong><br>' +
              '由平台演示企业账号发布、经管理员审核通过后展示，' +
              '用于演示「企业发布 → 平台审核 → 学员投递 → 企业查看简历」的完整流程，' +
              '<strong>不是真实招聘信息</strong>，请勿据此做求职决策。</div></div>'
            : '';

        // 标签
        const tags = (job.requirements || []).slice(0, 4);
        if (job.category) tags.unshift(job.category);
        const tagsHtml = tags.map(t => `<span class="emp-tag">${t}</span>`).join('');

        // 信息网格
        const infoItems = [
            { icon: 'fa-map-marker-alt', label: '工作地点', value: job.location || '广东' },
            { icon: 'fa-graduation-cap', label: '学历要求', value: job.education || '不限' },
            { icon: 'fa-briefcase', label: '经验要求', value: job.experience || '不限' },
            { icon: 'fa-clock', label: '工作类型', value: job.job_type || '全职' },
            { icon: 'fa-building', label: '公司规模', value: job.company_size || '未知' },
            { icon: 'fa-industry', label: '所属行业', value: job.industry || '未知' },
        ];
        const infoGridHtml = infoItems.map(item => `
            <div class="emp-detail-info-item">
                <i class="fas ${item.icon}"></i>
                <div>
                    <div class="emp-detail-info-label">${item.label}</div>
                    <div class="emp-detail-info-value">${item.value}</div>
                </div>
            </div>
        `).join('');

        // 职位亮点（从描述中提取关键点生成）
        const highlights = [];
        if (job.salary) highlights.push('有竞争力的薪资待遇');
        if (job.experience === '不限') highlights.push('接受无经验者，提供培训');
        if (job.education === '不限') highlights.push('学历不限，能力优先');
        if (job.company_size && parseInt(job.company_size) >= 100) highlights.push('大平台，发展空间大');
        if (job.description && job.description.includes('包')) highlights.push('提供食宿或相关补贴');
        const highlightsHtml = highlights.length > 0 ? `
            <div class="emp-detail-section">
                <h4><i class="fas fa-star" style="color:#d9a227;margin-right:6px;"></i>职位亮点</h4>
                <div class="emp-detail-highlights">
                    ${highlights.map(h => `<div class="emp-detail-highlight-item"><i class="fas fa-check-circle"></i>${h}</div>`).join('')}
                </div>
            </div>
        ` : '';

        // 相似职位
        const similarHtml = similar.length > 0 ? `
            <div class="emp-detail-section">
                <h4>相似职位推荐</h4>
                <div class="emp-similar-jobs">
                    ${similar.map(s => `
                        <div class="emp-similar-job-item" data-job-id="${s.id}">
                            <div>
                                <span class="emp-similar-job-title">${s.title}</span>
                                <span class="emp-similar-job-company">${s.company} · ${s.location || '广东'}</span>
                            </div>
                            <span class="emp-similar-job-salary">${s.salary}</span>
                        </div>
                    `).join('')}
                </div>
            </div>
        ` : '';

        showDetailModal('职位详情', `
            ${demoNotice}
            <div class="emp-detail-header">
                <h2>${job.title}</h2>
                <span class="emp-detail-salary">${job.salary}</span>
                <div class="emp-detail-tags">${tagsHtml}</div>
                ${dateStr ? `<div class="emp-detail-posted"><i class="fas fa-clock"></i> ${dateStr}</div>` : ''}
            </div>

            <div class="emp-detail-company">
                <div class="emp-company-logo-lg">${initial}</div>
                <div class="emp-detail-company-info">
                    <h4>${job.company}</h4>
                    <p>${job.company_size || ''} ${job.industry ? '· ' + job.industry : ''} ${job.location ? '· ' + job.location : ''}</p>
                </div>
            </div>

            <div class="emp-detail-section">
                <h4>职位信息</h4>
                <div class="emp-detail-info-grid">
                    ${infoGridHtml}
                </div>
            </div>

            <div class="emp-detail-section">
                <h4>职位描述</h4>
                <div class="emp-detail-desc">${job.description || '暂无详细描述'}</div>
            </div>

            ${reqsList ? `
            <div class="emp-detail-section">
                <h4>任职要求</h4>
                <ul class="emp-detail-reqs">${reqsList}</ul>
            </div>` : ''}

            ${highlightsHtml}

            <div class="emp-detail-section">
                <h4><i class="fas fa-lightbulb" style="color:#d9a227;margin-right:6px;"></i>申请建议</h4>
                <div class="emp-detail-tips">
                    <p>1. 确保简历中突出了与该岗位相关的技能和经验</p>
                    <p>2. 如持有相关证书，请在简历中标注</p>
                    <p>3. 申请后可在"我的求职"中查看审核进度</p>
                </div>
            </div>

            ${similarHtml}

            <div class="emp-detail-actions">
                <button class="btn btn-primary emp-detail-apply" data-job-id="${job.id}">
                    <i class="fas fa-paper-plane"></i> 立即申请
                </button>
                <button class="btn btn-outline emp-detail-save" data-job-id="${job.id}">
                    <i class="far fa-heart"></i> 收藏职位
                </button>
            </div>
        `);

        // 绑定弹窗内事件
        document.querySelector('.emp-detail-apply')?.addEventListener('click', async () => {
            await applyForJob(job.id);
        });
        document.querySelector('.emp-detail-save')?.addEventListener('click', async (e) => {
            await toggleSaveJob(job.id, e.currentTarget);
        });
        document.querySelectorAll('.emp-similar-job-item').forEach(item => {
            item.addEventListener('click', () => {
                document.querySelector('.modal-close')?.click();
                setTimeout(() => openJobDetail(item.dataset.jobId), 200);
            });
        });
    } catch(e) {
        showNotification('加载职位详情失败', 'error');
    }
}

/* 公开招聘公告详情。
   数据来自列表缓存（后端一次下发全字段），不再打接口。
   关键差异：**没有「立即申请」** —— 报名要去发布单位官方系统，本站只做信息聚合，
   所以主按钮是「前往公告原文」外链（新窗口打开，带 rel=noopener）。 */
function openRecruitDetail(key) {
    const r = RECRUIT_CACHE[key];
    if (!r) {
        showNotification('公告信息已失效，请重新加载列表', 'error');
        return;
    }
    // 意向按钮的初始态依赖已登记集合；首次打开时先补一次，避免「已登记却显示未登记」
    if (MY_INTENT_KEYS === null && AppState.user) {
        preloadIntentKeys().then(() => openRecruitDetail(key));
        return;
    }
    const cls = RECRUIT_STATUS_CLS[r.status] || 'rec-unknown';
    const rows = [
        ['发布单位', r.org],
        ['地区', r.region],
        ['岗位类别', r.category],
        ['用工性质', r.job_type],
        ['招聘人数', r.headcount],
        ['学历要求', r.education],
        ['其他条件', r.experience],
        ['薪酬待遇', r.salary],
        ['报名时间', (r.signup_start ? r.signup_start + ' 至 ' : '') + (r.deadline || '')],
        ['报名方式', r.signup_way],
        ['咨询方式', r.contact],
        ['发布日期', r.publish_date],
    ].filter(x => x[1]);
    const infoHtml = rows.map(([k, v]) =>
        `<div class="emp-recruit-row"><span class="emp-recruit-k">${escapeHtml(k)}</span><span class="emp-recruit-v">${escapeHtml(v)}</span></div>`
    ).join('');
    const srcHtml = (r.sources || []).map(s => `
        <li>
            <a href="${attrEsc(s.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(s.title || s.url)}</a>
            <span class="emp-recruit-src-meta">${escapeHtml([s.media, s.date].filter(Boolean).join(' · '))}</span>
        </li>`).join('');
    const note = (r.status === 'closed')
        ? '该公告报名已结束，信息仅供了解岗位与条件；如需跟进，请留意发布单位的下一轮公告。'
        : (RECRUIT_NOTES.disclaimer || '岗位条件、报名时间以发布单位公告原文为准；本平台不代办报名。');

    // 求职意向登记：平台只记录意向，**不代办报名** —— 主按钮始终是官方原文外链
    const canIntent = r.status === 'open' || r.status === 'upcoming';
    const intentOk = !!(MY_INTENT_KEYS && MY_INTENT_KEYS.has(r.key));
    const intentBlock = canIntent ? `
        <div class="emp-recruit-intent-box">
            <div class="emp-recruit-intent-tip">
                <i class="fas fa-circle-info"></i>
                想让平台记住你的意向、方便后续查看？可以登记求职意向。
                <strong>报名仍需你按上方「前往公告原文」自行完成，本平台不代办报名。</strong>
            </div>
            <button class="btn btn-outline emp-recruit-intent ${intentOk ? 'active' : ''}" data-recruit-key="${attrEsc(r.key)}">
                <i class="far fa-bookmark"></i> ${intentOk ? '已登记意向（点击取消）' : '登记求职意向'}
            </button>
        </div>` : '';

    showDetailModal('公开招聘公告', `
        <div class="emp-recruit-detail">
            <div class="emp-recruit-detail-head">
                <h2>${escapeHtml(r.title)}</h2>
                <span class="emp-recruit-status ${cls}">${escapeHtml(r.status_label)}</span>
            </div>
            <div class="emp-recruit-info">${infoHtml}</div>
            <div class="emp-detail-section">
                <h4>公告内容摘要</h4>
                <div class="emp-detail-desc">${escapeHtml(r.description || '详见公告原文')}</div>
            </div>
            <div class="emp-detail-section">
                <h4>资料来源</h4>
                <ul class="emp-recruit-src">${srcHtml}</ul>
            </div>
            <div class="emp-recruit-note">${escapeHtml(note)}</div>
            ${intentBlock}
            <div class="emp-detail-actions">
                <a class="btn btn-primary" href="${attrEsc((r.sources && r.sources[0] && r.sources[0].url) || '#')}" target="_blank" rel="noopener noreferrer">
                    <i class="fas fa-external-link-alt"></i> 前往公告原文
                </a>
            </div>
        </div>
    `);

    const intentBtn = document.querySelector('.emp-recruit-intent');
    if (intentBtn) {
        intentBtn.addEventListener('click', async () => {
            await toggleJobIntent(r.key, intentBtn);
            const nowOn = MY_INTENT_KEYS && MY_INTENT_KEYS.has(r.key);
            intentBtn.classList.toggle('active', !!nowOn);
            intentBtn.innerHTML = '<i class="far fa-bookmark"></i> ' +
                (nowOn ? '已登记意向（点击取消）' : '登记求职意向');
        });
    }
}

async function applyForJob(jobId) {
    if (!AppState.user) {
        showNotification('请先登录', 'error', { actionLabel: '去登录', action: openLoginModal });
        return;
    }
    try {
        const data = await apiCall('/api/employment/apply', 'POST', {
            user_id: AppState.user.id,
            job_id: parseInt(jobId)
        });
        if (data.success && data.has_resume === false) {
            // 申请成功但一条简历都没写 —— 企业端看到的其实是「空申请」，必须当场说明，
            // 否则学员会以为简历已经随申请投出去了（2026-10-07）。
            showNotification(data.message + ' · 你还没有填写简历，企业看不到简历内容', 'success');
            return;
        }
        showNotification(data.message, data.success ? 'success' : 'error');
    } catch(e) {
        showNotification('申请失败', 'error');
    }
}

async function toggleSaveJob(jobId, btnEl) {
    if (!AppState.user) {
        showNotification('请先登录', 'error', { actionLabel: '去登录', action: openLoginModal });
        return;
    }
    const isSaved = btnEl.classList.contains('saved') || btnEl.querySelector('.fas.fa-heart');
    try {
        if (isSaved) {
            await apiCall('/api/employment/save', 'DELETE', {
                user_id: AppState.user.id,
                job_id: parseInt(jobId)
            });
            btnEl.classList.remove('saved');
            const icon = btnEl.querySelector('i');
            if (icon) { icon.classList.remove('fas'); icon.classList.add('far'); }
            showNotification('已取消收藏', 'success');
        } else {
            await apiCall('/api/employment/save', 'POST', {
                user_id: AppState.user.id,
                job_id: parseInt(jobId)
            });
            btnEl.classList.add('saved');
            const icon = btnEl.querySelector('i');
            if (icon) { icon.classList.remove('far'); icon.classList.add('fas'); }
            showNotification('收藏成功', 'success');
        }
    } catch(e) {
        showNotification('操作失败', 'error');
    }
}

/* ============ 我的求职：公开招聘意向 + 企业岗位投递 ============
   两条通道的数据结构完全不同：
     · 企业岗位投递 → job_applications，挂在数字 job_id 上，企业端「简历管理」可见并给反馈；
     · 公开招聘意向 → job_intents，挂在公告的字符串 key 上，**平台不代办报名**。
   后端 /api/employment/my-jobs 一次下发两组，前端分别渲染并如实标注通道。 */

// 已登记的公告 key 集合（用于公告详情页判断按钮态）。懒加载 + 登记后即时更新。
let MY_INTENT_KEYS = null;

// 会话失效（401/403）时的统一提示：重试无用，引导重新登录
const SESSION_TIP_MY_JOBS = '<div class="emp-empty emp-empty-inline"><i class="fas fa-user-lock"></i>' +
    '<p>登录已过期，请重新登录后再查看求职记录</p></div>';

/* 懒加载意向 key 集合。老后端没有聚合接口时视为「无意向」，不阻断详情页渲染。 */
async function preloadIntentKeys() {
    if (MY_INTENT_KEYS !== null || !AppState.user) return;
    try {
        const d = await apiCall(`/api/employment/my-jobs/${AppState.user.id}`);
        MY_INTENT_KEYS = new Set(((d && d.intents) || []).map(i => i.recruit_key));
    } catch (e) {
        MY_INTENT_KEYS = new Set();
    }
}

async function loadMyJobs(statusFilter) {
    const intentEl = document.getElementById('emp-intent-list');
    const appEl = document.getElementById('emp-app-list');

    if (!AppState.user) {
        const tip = '<div class="emp-empty emp-empty-inline"><i class="fas fa-user-lock"></i>' +
                    '<p>登录后可查看投递记录与求职意向</p></div>';
        if (intentEl) intentEl.innerHTML = tip;
        if (appEl) appEl.innerHTML = '';
        return;
    }

    if (intentEl) showSkeleton(intentEl, 'row', 1);
    if (appEl) showSkeleton(appEl, 'row', 2);

    let apps = null, intents = null;
    // null = 未知（老后端没这个字段）→ 不下「你没写简历」的判断，宁缺勿错
    let hasResume = null;
    try {
        const d = await apiCall(`/api/employment/my-jobs/${AppState.user.id}`);
        if (d.success) {
            apps = d.applications || [];
            intents = d.intents || [];
            hasResume = (typeof d.has_resume === 'boolean') ? d.has_resume : null;
        }
    } catch (e) {
        const st = e && e.status;
        // 「新前端 + 旧后端」兜底：聚合接口是新增的，老后端没有 → 退回旧接口，意向区置空
        if (st !== 404 && st !== 405) {
            if (intentEl) intentEl.innerHTML = '';
            // 会话类错误（未登录/非本人）重试没有意义 → 给可操作的提示，不挂「重试」按钮
            if (st === 401 || st === 403) {
                if (appEl) appEl.innerHTML = SESSION_TIP_MY_JOBS;
            } else {
                showErrorState(appEl, '加载求职记录失败', () => loadMyJobs(statusFilter));
            }
            return;
        }
    }
    if (apps === null) {
        try {
            const params = statusFilter && statusFilter !== 'all' ? `?status=${statusFilter}` : '';
            const old = await apiCall(`/api/employment/applications/${AppState.user.id}${params}`);
            apps = old.success ? (old.applications || []) : [];
        } catch (e) {
            const st = e && e.status;
            if (st === 401 || st === 403) {
                if (appEl) appEl.innerHTML = SESSION_TIP_MY_JOBS;
            } else {
                showErrorState(appEl, '加载投递记录失败', () => loadMyJobs(statusFilter));
            }
            return;
        }
        intents = [];
    }

    MY_INTENT_KEYS = new Set(intents.map(i => i.recruit_key));

    // 状态筛选（聚合接口一次取全量，筛选在本地做，省一次请求）
    if (statusFilter && statusFilter !== 'all') {
        apps = apps.filter(a => a.status === statusFilter);
    }

    // —— 意向区 ——
    if (intentEl) {
        intents = intents.filter(i => i.recruit_key);
        if (!intents.length) {
            intentEl.innerHTML = '<div class="emp-empty emp-empty-inline"><i class="far fa-bookmark"></i>' +
                '<p>还没有登记求职意向</p>' +
                '<span class="emp-empty-sub">在「全部职位」里打开任意一条公开招聘公告，点「登记求职意向」即可</span></div>';
        } else {
            intentEl.innerHTML = intents.map(renderIntentCard).join('');
        }
    }

    // —— 投递区 ——
    if (appEl) {
        if (!apps.length) {
            // 修掉原先的死循环引导（「去投递心仪的职位吧」点过去只有不能投递的公告）
            // ⚠️ 旧文案写「先完善『我的简历』…即可一键投递」，暗示**必须先有简历才能投**，
            // 而实际不写简历也能投（只记一条申请 + 给积分）→ 文案与行为不一致（2026-10-07）。
            showEmptyState(appEl, 'fa-paper-plane', '暂无企业岗位投递记录',
                '在「全部职位」里找到合适的岗位，点卡片上的「申请职位」即可；建议先到「我的简历」填好简历，企业才能看到你的信息');
        } else {
            appEl.innerHTML = apps.map(app => renderApplicationCard(app, hasResume)).join('');
        }
    }
}

function renderIntentCard(it) {
    const cls = RECRUIT_STATUS_CLS[it.status] || 'rec-unknown';
    const deadlineTxt = it.deadline ? ('报名截止 ' + it.deadline) : '报名时间以公告原文为准';
    return `
    <div class="emp-intent-card" data-recruit-key="${attrEsc(it.recruit_key)}">
        <div class="emp-intent-main">
            <div class="emp-intent-head">
                <span class="emp-intent-title">${escapeHtml(it.title)}</span>
                <span class="emp-recruit-status ${cls}">${escapeHtml(it.status_label || '')}</span>
            </div>
            <div class="emp-intent-meta">
                ${escapeHtml(it.org || '')}${it.region ? '<span class="emp-dot">·</span>' + escapeHtml(it.region) : ''}
                <span class="emp-dot">·</span>${escapeHtml(deadlineTxt)}
            </div>
            ${it.note ? `<div class="emp-intent-note">备注：${escapeHtml(it.note)}</div>` : ''}
            <div class="emp-intent-disclaimer">
                <i class="fas fa-circle-info"></i> 本站仅记录意向，<strong>不代办报名</strong>，请按公告原文自行报名。
            </div>
        </div>
        <div class="emp-intent-actions">
            <button class="btn btn-outline btn-sm emp-intent-view" data-recruit-key="${attrEsc(it.recruit_key)}">查看公告</button>
            <button class="btn btn-outline btn-sm emp-intent-drop" data-recruit-key="${attrEsc(it.recruit_key)}">取消意向</button>
        </div>
    </div>`;
}

/* 登记 / 取消求职意向。want === false 时强制取消。
   ⚠️ 成功提示必须带上「不代办报名」，避免学员以为登记 = 已报名。 */
async function toggleJobIntent(key, btnEl, want) {
    if (!AppState.user) {
        showNotification('请先登录', 'error', { actionLabel: '去登录', action: openLoginModal });
        return;
    }
    const currently = MY_INTENT_KEYS ? MY_INTENT_KEYS.has(key) : false;
    const shouldAdd = (want === undefined) ? !currently : want;
    try {
        if (shouldAdd) {
            const d = await apiCall('/api/employment/intent', 'POST', {
                user_id: AppState.user.id, recruit_key: key
            });
            if (MY_INTENT_KEYS) MY_INTENT_KEYS.add(key);
            showNotification(d.message + '（' + (d.notice || '本平台不代办报名') + '）', 'success');
        } else {
            await apiCall('/api/employment/intent', 'DELETE', {
                user_id: AppState.user.id, recruit_key: key
            });
            if (MY_INTENT_KEYS) MY_INTENT_KEYS.delete(key);
            showNotification('已取消意向登记', 'success');
        }
        // 详情弹窗里的按钮态同步刷新
        document.querySelectorAll('.emp-recruit-intent').forEach(b => {
            if (b.dataset.recruitKey === key) b.classList.toggle('active', shouldAdd);
        });
        if (btnEl) btnEl.classList.toggle('active', shouldAdd);
        // 意向区若已渲染过，刷新一次（此时它在后台，不打断当前操作）
        if (document.getElementById('emp-intent-list') &&
            document.querySelector('.emp-tab.active') &&
            document.querySelector('.emp-tab.active').dataset.empTab === 'applications') {
            loadMyJobs();
        }
    } catch (e) {
        const code = e && e.code;
        if (code === 'not_found') showNotification('该公告已下架，无法登记意向', 'error');
        else showNotification('操作失败，请稍后重试', 'error');
    }
}

/* ============ 我的简历 ============
   用法口径（与全项目「不编造」红线一致）：
     · 「能力档案」区展示的是**平台里真实存在的**学习数据，也是 AI 写作的唯一素材；
     · AI 只能在素材范围内组织与润色，未提供的信息一律给【待补充】占位；
     · AI 起草后按钮旁会出现「已用 AI 起草」标注，不隐瞒 AI 参与。 */

let RESUME_CACHE = { profile: null, resume: null };

function setupResumePanel() {
    const addBtn = document.getElementById('resume-add-exp');
    if (addBtn) addBtn.addEventListener('click', () => addExpRow({}));

    const saveBtn = document.getElementById('resume-save');
    if (saveBtn) saveBtn.addEventListener('click', saveResumeForm);

    const printBtn = document.getElementById('resume-print');
    if (printBtn) printBtn.addEventListener('click', printResume);

    const copyBtn = document.getElementById('resume-copy');
    if (copyBtn) copyBtn.addEventListener('click', copyResumeText);

    // AI 按钮用事件委托，覆盖动态生成的「经历润色」按钮
    document.querySelectorAll('.resume-ai-btn').forEach(btn => {
        if (btn.dataset.bound) return;
        btn.dataset.bound = '1';
        btn.addEventListener('click', () => aiDraftResume(btn.dataset.aiSection, btn));
    });
    const expList = document.getElementById('resume-exp-list');
    if (expList) {
        expList.addEventListener('click', (e) => {
            const aiBtn = e.target.closest('.resume-exp-ai');
            if (aiBtn) { aiDraftResume('experience', aiBtn); return; }
            const delBtn = e.target.closest('.resume-exp-del');
            if (delBtn) {
                const row = delBtn.closest('.resume-exp-row');
                if (row) row.remove();
            }
        });
    }

    const intentEl = document.getElementById('emp-intent-list');
    if (intentEl) {
        // 意向区内容会被反复重建，这里用事件委托绑定一次即可（避免每次 render 后重复绑定）
        intentEl.addEventListener('click', (e) => {
            const view = e.target.closest('.emp-intent-view');
            const drop = e.target.closest('.emp-intent-drop');
            if (view) { e.stopPropagation(); openRecruitDetail(view.dataset.recruitKey); }
            if (drop) { e.stopPropagation(); toggleJobIntent(drop.dataset.recruitKey, null, false); }
        });
    }
}

/* 打开登录弹窗。全站触发方式统一走这里（原来是各处手写 classList.remove('is-hidden')，
   漏一处就是一个「点了没反应」的按钮）。 */
function openLoginModal() {
    const m = document.getElementById('login-modal');
    if (!m) return;
    m.classList.remove('is-hidden');
}

/* 给容器内所有「去登录」按钮绑事件（用 data 属性选择，幂等：重复调用不会叠加监听——
   innerHTML 每次重设会重建节点，绑定随之失效，所以每次渲染后都要重新调一次）。 */
function bindLoginCta(root) {
    if (!root) return;
    root.querySelectorAll('[data-login-cta]').forEach(btn => {
        btn.addEventListener('click', e => { e.stopPropagation(); openLoginModal(); });
    });
}

async function loadResumePanel() {
    const noteEl = document.getElementById('resume-note');
    const profEl = document.getElementById('resume-profile');
    if (!AppState.user) {
        if (noteEl) {
            noteEl.className = 'resume-note is-warn';
            // ⚠️ 旧文案只说「登录后可创建并保存你的简历」，而表单本身**是可填的**
            // （输入框未 disabled），学员填完点保存才被告知要登录，白填一场。
            // 这里把「不会保存」直接写在最前面，并给一个真的能点的入口（2026-10-07）。
            noteEl.innerHTML = '<i class="fas fa-user-lock"></i> 你还未登录：' +
                '<strong>这里填写的内容不会被保存</strong>，「AI 起草」与「保存简历」都会提示登录。' +
                '<button class="btn btn-primary btn-sm emp-login-cta" data-login-cta="1">去登录</button>';
            bindLoginCta(noteEl);
        }
        if (profEl) profEl.innerHTML = '';
        return;
    }
    try {
        if (profEl) showSkeleton(profEl, 'row', 4);
        const [profData, resumeData] = await Promise.all([
            apiCall(`/api/employment/profile/${AppState.user.id}`),
            apiCall(`/api/employment/resume/${AppState.user.id}`)
        ]);
        RESUME_CACHE.profile = profData.success ? profData.profile : null;
        RESUME_CACHE.resume = resumeData.success ? resumeData.resume : null;
        renderResumeProfile(RESUME_CACHE.profile);
        fillResumeForm(RESUME_CACHE.resume);
    } catch (e) {
        const status = e && e.status;
        // 会话类错误与网络/服务错误要分开：前者重试必然还是失败，给「重新登录」的指引更有用
        const isSession = (status === 401 || status === 403);
        const msg = status === 401 ? '登录已过期，请重新登录后再查看简历。'
                  : status === 403 ? '只能查看本人的简历资料。'
                  : '简历加载失败，请稍后重试。';
        if (profEl) {
            profEl.innerHTML = '<div class="resume-profile-error"><i class="fas fa-triangle-exclamation"></i>' +
                '<p>' + (isSession ? '未获取到你的能力档案' : '能力档案加载失败') + '</p></div>';
        }
        if (noteEl) {
            noteEl.className = 'resume-note is-error';
            noteEl.innerHTML = '<i class="fas fa-triangle-exclamation"></i> ' + msg +
                (isSession ? '' : '<button class="btn btn-outline btn-sm resume-retry">重试</button>');
            noteEl.querySelector('.resume-retry')?.addEventListener('click', loadResumePanel);
        }
    }
}

function renderResumeProfile(p) {
    const el = document.getElementById('resume-profile');
    if (!el) return;
    if (!p) { el.innerHTML = ''; return; }

    const certHtml = (p.certificates || []).map(c => {
        let cls = 'is-locked', label = '未开始';
        if (c.earned) { cls = 'is-earned'; label = '已获得'; }
        else if (c.status === 'in_progress') { cls = 'is-progress'; label = '学习中 ' + (c.progress || 0) + '%'; }
        return `<li class="resume-cert ${cls}">
            <span class="resume-cert-name">${escapeHtml(c.name)}</span>
            <span class="resume-cert-status">${escapeHtml(label)}${c.earned && c.date ? ' · ' + escapeHtml(c.date) : ''}</span>
        </li>`;
    }).join('');

    const trainingHtml = (p.training || []).map(t => `
        <li class="resume-training">
            <span>${escapeHtml(t.title)}</span>
            <span class="resume-training-score">${t.scored ? escapeHtml(String(t.score)) + ' 分' : '待老师批改'}</span>
        </li>`).join('');

    el.innerHTML = `
        <div class="resume-profile-head">
            <i class="fas fa-id-card"></i>
            <div>
                <h4>能力档案</h4>
                <p>平台记录的真实学习数据</p>
            </div>
        </div>
        <ul class="resume-profile-list">
            <li><span>姓名</span><b>${escapeHtml((p.basic && p.basic.name) || '未填写')}</b></li>
            <li><span>学习方向</span><b>${escapeHtml((p.learning && p.learning.direction) || '未填写')}</b></li>
            <li><span>课程完成度</span><b>${p.learning ? escapeHtml(String(p.learning.progress)) + '%' : '—'}</b></li>
            <li><span>学习积分</span><b>${escapeHtml(String(p.points || 0))}</b></li>
        </ul>
        ${certHtml ? `<div class="resume-profile-sub"><i class="fas fa-certificate"></i> 学习证书</div>
            <ul class="resume-cert-list">${certHtml}</ul>` : ''}
        ${trainingHtml ? `<div class="resume-profile-sub"><i class="fas fa-flask"></i> 实训成绩</div>
            <ul class="resume-training-list">${trainingHtml}</ul>` : ''}
        <div class="resume-profile-foot">
            以上为 AI 起草时可使用的全部素材；档案里没有的内容，AI 不会替你编造。
        </div>`;
}

function fillResumeForm(r) {
    r = r || {};
    const set = (id, v) => { const el = document.getElementById(id); if (el) el.value = v || ''; };
    set('resume-title', r.title);
    set('resume-region', r.region);
    set('resume-education', r.education);
    set('resume-work-years', r.work_years);
    set('resume-phone', r.phone || (AppState.user && AppState.user.phone) || '');
    set('resume-email', r.email || (AppState.user && AppState.user.email) || '');
    set('resume-self-eval', r.self_eval);
    set('resume-skills', r.skills);
    renderExpList(Array.isArray(r.experience) ? r.experience : []);

    const noteEl = document.getElementById('resume-note');
    if (noteEl) {
        noteEl.className = 'resume-note' + (r.ai_used ? ' is-ai' : '');
        noteEl.innerHTML = r.ai_used
            ? '<i class="fas fa-wand-magic-sparkles"></i> 这份简历使用过 <strong>AI 辅助起草</strong>。' +
              'AI 只根据你的平台学习数据组织文字，<strong>请逐项核对事实</strong>后再用于投递。'
            : '<i class="fas fa-shield-halved"></i> AI 起草只会使用左侧「能力档案」里的真实数据，' +
              '未提供的信息会以【待补充】占位，不会替你编造。';
    }
}

function renderExpList(list) {
    const el = document.getElementById('resume-exp-list');
    if (!el) return;
    el.innerHTML = '';
    if (!list.length) {
        el.innerHTML = '<p class="resume-hint">还没有添加经历。没有也可以留空 —— 平台不会替你补。</p>';
        return;
    }
    list.forEach(item => addExpRow(item));
}

function addExpRow(item) {
    const el = document.getElementById('resume-exp-list');
    if (!el) return;
    if (el.querySelector('.resume-hint') && !el.querySelector('.resume-exp-row')) el.innerHTML = '';
    item = item || {};
    const row = document.createElement('div');
    row.className = 'resume-exp-row';
    row.innerHTML = `
        <div class="resume-exp-grid">
            <input type="text" class="exp-company" name="exp_company" autocomplete="off" placeholder="单位 / 合作社名称" value="${attrEsc(item.company || '')}">
            <input type="text" class="exp-position" name="exp_position" autocomplete="off" placeholder="担任角色" value="${attrEsc(item.position || '')}">
            <input type="text" class="exp-period" name="exp_period" autocomplete="off" placeholder="时间，如 2024-2025" value="${attrEsc(item.period || '')}">
        </div>
        <textarea class="exp-desc" name="exp_desc" rows="2" placeholder="做了什么、学到什么（可点右侧「AI 润色」改善表达）">${escapeHtml(item.desc || '')}</textarea>
        <div class="resume-exp-actions">
            <button type="button" class="btn btn-outline btn-sm resume-exp-ai" data-ai-section="experience">
                <i class="fas fa-wand-magic-sparkles"></i> AI 润色
            </button>
            <button type="button" class="btn btn-outline btn-sm resume-exp-del">删除</button>
        </div>`;
    el.appendChild(row);
}

function collectResumeForm() {
    const val = (id) => { const el = document.getElementById(id); return el ? el.value.trim() : ''; };
    const experience = [];
    document.querySelectorAll('#resume-exp-list .resume-exp-row').forEach(row => {
        const g = (sel) => { const el = row.querySelector(sel); return el ? el.value.trim() : ''; };
        const company = g('.exp-company'), position = g('.exp-position');
        const period = g('.exp-period'), desc = g('.exp-desc');
        if (company || position || period || desc) experience.push({ company, position, period, desc });
    });
    return {
        title: val('resume-title'),
        region: val('resume-region'),
        education: val('resume-education'),
        work_years: val('resume-work-years'),
        phone: val('resume-phone'),
        email: val('resume-email'),
        self_eval: val('resume-self-eval'),
        skills: val('resume-skills'),
        experience
    };
}

async function saveResumeForm() {
    if (!AppState.user) { showNotification('请先登录', 'error', { actionLabel: '去登录', action: openLoginModal }); return; }
    const btn = document.getElementById('resume-save');
    if (btn) btn.disabled = true;
    try {
        const d = await apiCall(`/api/employment/resume/${AppState.user.id}`, 'PUT', collectResumeForm());
        if (d.success) {
            RESUME_CACHE.resume = d.resume;
            showNotification('简历已保存', 'success');
        } else {
            showNotification(d.message || '保存失败', 'error');
        }
    } catch (e) {
        const st = e && e.status;
        showNotification(st === 401 ? '登录已过期，请重新登录'
                        : st === 403 ? '只能修改本人的简历'
                        : '保存失败，请稍后重试', 'error');
    } finally {
        if (btn) btn.disabled = false;
    }
}

/* AI 起草 / 润色单段。section ∈ self_eval | skills | experience */
async function aiDraftResume(section, btn) {
    if (!AppState.user) { showNotification('请先登录', 'error', { actionLabel: '去登录', action: openLoginModal }); return; }

    let draft = '', targetSel = '';
    if (section === 'self_eval') { draft = document.getElementById('resume-self-eval')?.value.trim() || ''; targetSel = '#resume-self-eval'; }
    else if (section === 'skills') { draft = document.getElementById('resume-skills')?.value.trim() || ''; targetSel = '#resume-skills'; }
    else {
        const row = btn && btn.closest('.resume-exp-row');
        if (!row) { showNotification('未找到对应的经历条目', 'error'); return; }
        const g = (sel) => { const el = row.querySelector(sel); return el ? el.value.trim() : ''; };
        if (!g('.exp-company') && !g('.exp-position') && !g('.exp-desc')) {
            showNotification('请先填写这条经历的单位或内容 —— AI 不会凭空编造经历', 'error');
            return;
        }
        draft = [g('.exp-company'), g('.exp-position'), g('.exp-period'), g('.exp-desc')]
            .filter(Boolean).join(' / ');
        targetSel = null;
    }

    const oldHtml = btn ? btn.innerHTML : '';
    if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 生成中'; }
    try {
        const d = await apiCall('/api/employment/resume/ai', 'POST', {
            user_id: AppState.user.id, section, draft
        });
        if (!d.success) {
            showNotification(d.message || 'AI 生成失败', 'error');
            return;
        }
        if (section === 'experience') {
            const row = btn.closest('.resume-exp-row');
            const ta = row.querySelector('.exp-desc');
            if (ta) ta.value = d.text;
            row.querySelector('.exp-desc').focus();
        } else {
            const el = document.querySelector(targetSel);
            if (el) el.value = d.text;
        }
        const flag = document.querySelector(`.resume-ai-flag[data-ai-flag="${section}"]`);
        if (flag) flag.innerHTML = '<i class="fas fa-wand-magic-sparkles"></i> 已用 AI 起草 · 请核对事实';
        showNotification(d.notice || '已生成，请核对后再使用', 'success');
    } catch (e) {
        const code = e && e.code;
        if (code === 'ai_not_configured') showNotification('AI 辅助功能尚未启用，请联系管理员（12316）', 'error');
        else if (code === 'rate_limited') showNotification('AI 使用过于频繁，请稍后再试', 'error');
        else if (code === 'draft_too_long') showNotification('这一条内容过长，请精简后再试', 'error');
        else showNotification(e && e.status === 401 ? '登录已过期，请重新登录' : 'AI 服务暂时不可用，请稍后重试', 'error');
    } finally {
        if (btn) { btn.disabled = false; btn.innerHTML = oldHtml; }
    }
}

function resumeToText() {
    const d = collectResumeForm();
    const p = RESUME_CACHE.profile || {};
    const basic = p.basic || {};
    const L = [];
    L.push((basic.name || '（姓名未填写）') + '　个人简历');
    L.push('');
    const head = [
        ['求职意向', d.title], ['期望地区', d.region], ['最高学历', d.education],
        ['工作年限', d.work_years], ['联系电话', d.phone], ['电子邮箱', d.email],
    ].filter(x => x[1]);
    if (head.length) { L.push('【基本信息】'); head.forEach(([k, v]) => L.push(k + '：' + v)); L.push(''); }

    if (d.self_eval) { L.push('【自我评价】'); L.push(d.self_eval); L.push(''); }
    if (d.skills) { L.push('【专业技能】'); L.push(d.skills); L.push(''); }
    if (d.experience.length) {
        L.push('【工作与实践经历】');
        d.experience.forEach(e => {
            L.push('- ' + [e.company, e.position, e.period].filter(Boolean).join(' · '));
            if (e.desc) L.push('  ' + e.desc);
        });
        L.push('');
    }
    const certs = (p.certificates || []).filter(c => c.earned);
    if (certs.length) {
        L.push('【平台学习证书（已获得）】');
        certs.forEach(c => L.push('- ' + c.name + (c.date ? '（' + c.date + '）' : '')));
        L.push('');
    }
    return L.join('\n');
}

function printResume() {
    if (!AppState.user) { showNotification('请先登录', 'error', { actionLabel: '去登录', action: openLoginModal }); return; }
    const text = resumeToText();
    const basic = (RESUME_CACHE.profile || {}).basic || {};
    const win = window.open('', '_blank');
    if (!win) { showNotification('浏览器拦截了新窗口，请允许弹出窗口后重试', 'error'); return; }
    win.document.write('<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">' +
        '<title>' + (basic.name || '个人简历') + ' - 个人简历</title><style>' +
        'body{font-family:"Microsoft YaHei",system-ui,sans-serif;line-height:1.9;color:#222;' +
        'max-width:720px;margin:40px auto;padding:0 24px;white-space:pre-wrap;font-size:14px;}' +
        '@media print{body{margin:0;max-width:none;}}' +
        '</style></head><body>' + escapeHtml(text) +
        '<script>window.onload=function(){window.print();}<\/script></body></html>');
    win.document.close();
}

function copyResumeText() {
    if (!AppState.user) { showNotification('请先登录', 'error', { actionLabel: '去登录', action: openLoginModal }); return; }
    const text = resumeToText();
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text)
            .then(() => showNotification('已复制简历纯文本', 'success'))
            .catch(() => showNotification('复制失败，请手动选择文本', 'error'));
    } else {
        showNotification('当前浏览器不支持一键复制，请用「打印 / 导出 PDF」', 'error');
    }
}

async function loadUserApplications(statusFilter) {
    if (!AppState.user) return;
    const listEl = document.getElementById('emp-app-list');
    if (!listEl) return;
    try {
        showSkeleton(listEl, 'row', 3);
        const params = statusFilter && statusFilter !== 'all' ? `?status=${statusFilter}` : '';
        const data = await apiCall(`/api/employment/applications/${AppState.user.id}${params}`);
        if (data.success) {
            if (data.applications.length === 0) {
                showEmptyState(listEl, 'fa-paper-plane', '暂无投递记录', '去投递心仪的职位吧');
            } else {
                listEl.innerHTML = data.applications.map(app => renderApplicationCard(app, null)).join('');
            }
        }
    } catch(e) {
        showErrorState(listEl, '加载投递记录失败', () => loadUserApplications(statusFilter));
    }
}

function renderApplicationCard(app, hasResume) {
    // ⚠️ 后端 enterprise_update_application 的白名单是 approved / rejected / **interview**，
    //   这里四个状态必须齐全 —— 漏掉 interview 时学员端会直接把英文原文显示出来（2026-10-09）。
    const statusMap = {
        'pending': { text: '待审核', class: 'pending' },
        'interview': { text: '已通知面试', class: 'interview' },
        'approved': { text: '已通过', class: 'approved' },
        'rejected': { text: '已拒绝', class: 'rejected' }
    };
    const status = statusMap[app.status] || statusMap.pending;
    // ⚠️ 旧文案第一步是「投递简历」、第二步是「简历审核中」—— 但学员点「申请职位」时
    // 平台**并没有**替他投出任何简历（可以一条简历都没写就申请成功）→ 会让人以为
    // 简历已经发出去了。改为如实描述「提交申请 / 企业查阅」（2026-10-07）。
    const timelineSteps = [
        { label: `提交申请 ${app.applied_at || ''}`, done: true },
        { label: '企业查阅中', done: app.status !== 'pending', active: app.status === 'pending' },
        { label: app.status === 'approved' ? '已通过审核' : app.status === 'rejected' ? '未通过审核'
                : app.status === 'interview' ? '已通知面试' : '面试安排',
          done: app.status === 'approved' || app.status === 'rejected' || app.status === 'interview',
          active: app.status === 'interview' }
    ];
    if (app.status === 'approved') timelineSteps[2].done = true;

    // hasResume === false 才提示（null = 老后端没下发，宁缺勿错）
    const noResumeNote = hasResume === false
        ? '<div class="emp-app-note"><i class="fas fa-triangle-exclamation"></i> ' +
          '你还没有填写简历，企业端暂时看不到你的简历内容 —— 建议现在到「我的简历」补充。</div>'
        : '';

    return `
    <div class="emp-app-card">
        <div class="emp-app-header">
            <h4>${escapeHtml(app.title || '')}</h4>
            <span class="emp-app-status ${status.class}">${status.text}</span>
        </div>
        <p class="emp-app-company">${escapeHtml(app.company || '')} · ${escapeHtml(app.location || '广东')}</p>
        <p class="emp-app-salary">${escapeHtml(app.salary || '')}</p>
        ${noResumeNote}
        <div class="emp-app-timeline">
            ${timelineSteps.map(step => `
                <div class="emp-timeline-item ${step.done ? 'done' : ''} ${step.active ? 'active' : ''}">
                    <span class="emp-timeline-dot"></span>
                    <span>${step.label}</span>
                </div>
            `).join('')}
        </div>
    </div>`;
}

async function loadSavedJobs() {
    if (!AppState.user) {
        // ⚠️ 旧版在这里直接 return —— 未登录点进「收藏职位」是一片空白，
        // 分不清「没收藏任何职位」还是「页面坏了」；而「我的求职」是有提示的，
        // 同一板块两种表现（2026-10-07）。这里补上同样的提示（放进列表容器，
        // 不覆盖 #emp-saved-empty 的默认文案，免得登录后残留）。
        const listEl0 = document.getElementById('emp-saved-list');
        const emptyEl0 = document.getElementById('emp-saved-empty');
        if (emptyEl0) emptyEl0.style.display = 'none';
        if (listEl0) {
            listEl0.innerHTML = '<div class="emp-empty emp-empty-inline"><i class="fas fa-user-lock"></i>' +
                '<p>登录后可收藏职位</p>' +
                '<span class="emp-empty-sub">登录后，在「全部职位」里点卡片右侧的爱心即可收藏</span>' +
                '<button class="btn btn-primary btn-sm emp-login-cta" data-login-cta="1">去登录</button></div>';
            bindLoginCta(listEl0);
        }
        return;
    }
    const listEl = document.getElementById('emp-saved-list');
    const emptyEl = document.getElementById('emp-saved-empty');
    if (!listEl) return;
    try {
        showSkeleton(listEl, 'card', 2);
        const savedData = await apiCall(`/api/employment/saved/${AppState.user.id}`);
        if (!savedData.success || savedData.saved_ids.length === 0) {
            listEl.innerHTML = '';
            if (emptyEl) emptyEl.style.display = 'block';
            return;
        }
        if (emptyEl) emptyEl.style.display = 'none';
        // 获取所有职位，过滤收藏的
        const jobsData = await apiCall('/api/employment/jobs');
        if (jobsData.success) {
            const savedJobs = jobsData.jobs.filter(j => savedData.saved_ids.includes(j.id));
            listEl.innerHTML = savedJobs.map(job => renderJobCard(job, savedData.saved_ids)).join('');
            bindJobCardEvents(listEl);
        }
    } catch(e) {
        showErrorState(listEl, '加载收藏失败', () => loadSavedJobs());
    }
}

function computeRelativeDate(dateStr) {
    if (!dateStr) return '';
    const now = new Date();
    const date = new Date(dateStr);
    const diff = Math.floor((now - date) / (1000 * 60 * 60 * 24));
    if (diff <= 0) return '今天发布';
    if (diff === 1) return '1天前发布';
    if (diff < 7) return `${diff}天前发布`;
    if (diff < 30) return `${Math.floor(diff / 7)}周前发布`;
    return dateStr;
}

function getCompanyInitial(companyName) {
    if (!companyName) return '企';
    return companyName.charAt(0);
}

// ==================== 教师面板 ====================

function setupTeacherPanel() {
    // 搜索框
    const searchInput = document.getElementById('teacher-search');
    let searchTimeout;
    searchInput?.addEventListener('input', function() {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => loadStudents(this.value), 300);
    });

    // 添加学员按钮
    document.getElementById('teacher-add-student-btn')?.addEventListener('click', () => {
        showAddStudentModal();
    });

    // AI报告 — 快捷标签填入
    const reportTextarea = document.getElementById('teacher-report-prompt');
    document.querySelectorAll('.suggestion-chip').forEach(chip => {
        chip.addEventListener('click', () => {
            if (reportTextarea) {
                reportTextarea.value = chip.dataset.q;
                reportTextarea.focus();
            }
        });
    });
    document.getElementById('teacher-report-generate-btn')?.addEventListener('click', () => generateTeacherReport());

    // 子标签切换
    setupTeacherTabs();

    // 通知公告
    document.getElementById('teacher-publish-ann-btn')?.addEventListener('click', showPublishAnnouncementModal);

}

// 可关联的学员账号（role=student 且未被任何名册行占用）—— 教师端两处表单共用
async function loadLinkableAccountsInto(selectId, hintId, currentUsername) {
    const sel = document.getElementById(selectId);
    if (!sel) return;
    sel.innerHTML = '<option value="">加载中…</option>';
    try {
        const data = await apiCall('/api/teacher/linkable-accounts');
        const list = (data && data.accounts) || [];
        const opts = [];
        if (currentUsername) {
            opts.push(`<option value="${escapeHtml(currentUsername)}">${escapeHtml(currentUsername)}（当前已关联）</option>`);
        } else {
            opts.push('<option value="">（不关联账号）</option>');
        }
        list.forEach(a => opts.push(`<option value="${escapeHtml(a.username)}">${escapeHtml(a.name || a.username)}（${escapeHtml(a.username)}）</option>`));
        if (!list.length && !currentUsername) opts.push('<option value="">（没有空闲的学员账号）</option>');
        if (currentUsername) opts.push('<option value="">（改为不关联账号）</option>');
        sel.innerHTML = opts.join('');
        const hint = hintId ? document.getElementById(hintId) : null;
        if (hint) {
            hint.textContent = list.length
                ? `只显示尚未被名册占用的学员账号，共 ${list.length} 个。`
                : '目前没有空闲的学员账号，可改用「新建账号」为学员开一个登录账号。';
        }
    } catch (e) {
        sel.innerHTML = '<option value="">账号列表加载失败</option>';
        const hint = hintId ? document.getElementById(hintId) : null;
        if (hint) hint.textContent = '账号列表加载失败，请关闭后重试（本次保存不会改动账号关联）。';
    }
}

// 名册「学习方向」的规范选项（唯一来源）。
// ⚠️ 编辑表单必须用 directionOptionsHtml(student.direction) 生成：如果学员现有方向
//    不在下面这张表里，直接 `select.value = 方向` 会落到空值，保存时把方向**静默清空**。
//    该助手会把「不在表里的现有值」原样追加一项，保证不会被改掉。
const STUDENT_DIRECTIONS = ['荔枝种植', '电商运营', '广绣工艺', '水产养殖'];
function directionOptionsHtml(current) {
    const list = STUDENT_DIRECTIONS.slice();
    const cur = current || '';
    if (cur && list.indexOf(cur) === -1) list.push(cur);
    return list.map(d => `<option value="${d}" ${d === cur ? 'selected' : ''}>${d}</option>`).join('');
}

function showAddStudentModal() {
    showDetailModal('添加学员', `
        <div class="teacher-form">
            <div class="form-group">
                <label>学员姓名</label>
                <input type="text" id="new-student-name" name="new-student-name" placeholder="输入姓名" autocomplete="off">
            </div>
            <div class="form-group">
                <label>学习方向</label>
                <select id="new-student-direction">
                    ${directionOptionsHtml('')}
                </select>
            </div>
            <div class="form-group">
                <label>平台账号</label>
                <select id="new-student-account-mode">
                    <option value="link">关联已有学员账号</option>
                    <option value="create">新建账号（我来设用户名和初始密码）</option>
                    <option value="none">暂不关联（该学员无法登录、收不到通知）</option>
                </select>
            </div>
            <div class="form-group" id="new-student-link-group">
                <label>选择要关联的账号</label>
                <select id="new-student-link-username"><option value="">加载中…</option></select>
                <div class="teacher-form-hint" id="new-student-link-hint"></div>
            </div>
            <div class="form-group" id="new-student-create-group" style="display:none">
                <label>用户名</label>
                <input type="text" id="new-student-new-username" name="new-student-new-username" placeholder="登录用，如 zhangsan" autocomplete="off">
                <label style="margin-top:8px;display:block">初始密码</label>
                <input type="text" id="new-student-new-password" name="new-student-new-password" placeholder="至少 6 位，请线下告知学员" autocomplete="off">
            </div>
            <button class="btn btn-primary teacher-form-submit" id="submit-add-student">
                <i class="fas fa-plus"></i> 确认添加
            </button>
        </div>
    `);
    loadLinkableAccountsInto('new-student-link-username', 'new-student-link-hint', '');
    const modeSel = document.getElementById('new-student-account-mode');
    modeSel?.addEventListener('change', () => {
        document.getElementById('new-student-link-group').style.display = modeSel.value === 'link' ? '' : 'none';
        document.getElementById('new-student-create-group').style.display = modeSel.value === 'create' ? '' : 'none';
    });
    document.getElementById('submit-add-student')?.addEventListener('click', async () => {
        const name = document.getElementById('new-student-name').value.trim();
        const direction = document.getElementById('new-student-direction').value;
        const mode = document.getElementById('new-student-account-mode').value;
        if (!name) { showNotification('请输入姓名', 'error'); return; }
        const payload = { name, direction };
        if (mode === 'link') {
            const u = document.getElementById('new-student-link-username').value;
            if (!u) { showNotification('请选择一个要关联的账号，或改选「暂不关联」', 'error'); return; }
            payload.link_username = u;
        } else if (mode === 'create') {
            const nu = document.getElementById('new-student-new-username').value.trim();
            const npw = document.getElementById('new-student-new-password').value.trim();
            if (!nu) { showNotification('请输入用户名', 'error'); return; }
            if (npw.length < 6) { showNotification('初始密码至少 6 位', 'error'); return; }
            payload.new_username = nu;
            payload.new_password = npw;
        }
        try {
            const data = await apiCall('/api/teacher/students/add', 'POST', payload);
            showNotification(data.message, data.success ? 'success' : 'error');
            if (data.success) {
                document.querySelector('.modal-overlay.detail-modal')?.remove();
                loadStudents();
                loadTeacherDashboard();
            }
        } catch(e) {
            showNotification('添加失败', 'error');
        }
    });
}

function showEditStudentModal(student) {
    const currentAccount = student.user_id || '';
    showDetailModal(`编辑学员 - ${student.name}`, `
        <div class="teacher-form">
            <div class="form-group">
                <label>学员姓名</label>
                <input type="text" id="edit-student-name" name="edit-student-name" value="${escapeHtml(student.name)}" autocomplete="off">
            </div>
            <div class="form-group">
                <label>学习方向</label>
                <select id="edit-student-direction">
                    ${directionOptionsHtml(student.direction)}
                </select>
            </div>
            <div class="form-group">
                <label>状态</label>
                <select id="edit-student-status">
                    <option value="active" ${student.status === 'active' ? 'selected' : ''}>在读</option>
                    <option value="suspended" ${student.status === 'suspended' ? 'selected' : ''}>停课</option>
                </select>
            </div>
            <div class="form-group">
                <label>平台账号</label>
                <select id="edit-student-link-username"><option value="">加载中…</option></select>
                <div class="teacher-form-hint" id="edit-student-link-hint"></div>
            </div>
            <div class="teacher-form-actions">
                <button class="btn btn-outline" id="cancel-edit-student">取消</button>
                <button class="btn btn-primary" id="submit-edit-student">
                    <i class="fas fa-check"></i> 保存修改
                </button>
            </div>
        </div>
    `);
    loadLinkableAccountsInto('edit-student-link-username', 'edit-student-link-hint', currentAccount);
    document.getElementById('cancel-edit-student')?.addEventListener('click', () => {
        document.querySelector('.modal-overlay.detail-modal')?.remove();
    });
    document.getElementById('submit-edit-student')?.addEventListener('click', async () => {
        const name = document.getElementById('edit-student-name').value.trim();
        if (!name) { showNotification('请输入姓名', 'error'); return; }
        const direction = document.getElementById('edit-student-direction').value;
        const status = document.getElementById('edit-student-status').value;
        const account = document.getElementById('edit-student-link-username').value;
        try {
            // 先存资料，账号关联单独走 link 接口（各自校验，避免半成功说不清）
            const data = await apiCall(`/api/teacher/students/${student.id}`, 'PUT', { name, direction, status });
            if (!data.success) { showNotification(data.message || '更新失败', 'error'); return; }
            if (account !== currentAccount) {
                const lr = await apiCall(`/api/teacher/students/${student.id}/link`, 'POST', { username: account });
                if (!lr.success) { showNotification(lr.message || '账号关联失败', 'error'); loadStudents(); return; }
                showNotification(lr.message, 'success');
            } else {
                showNotification('已保存', 'success');
            }
            document.querySelector('.modal-overlay.detail-modal')?.remove();
            loadStudents();
            loadTeacherDashboard();
        } catch(e) {
            showNotification('更新失败', 'error');
        }
    });
}

async function loadTeacherDashboard() {
    const statEls = {
        total: document.getElementById('stat-total-students'),
        certs: document.getElementById('stat-certificates'),
        completion: document.getElementById('stat-completion'),
        score: document.getElementById('stat-avg-score')
    };
    Object.values(statEls).forEach(el => { if (el) el.textContent = '...'; });
    try {
        const data = await apiCall('/api/teacher/dashboard');
        if (data.success) {
            const s = data.dashboard.stats;
            if (statEls.total) statEls.total.textContent = s.total_students;
            if (statEls.certs) statEls.certs.textContent = s.certificates_earned;
            if (statEls.completion) statEls.completion.textContent = s.completion_rate + '%';
            if (statEls.score) statEls.score.textContent = s.avg_score;
            // 最近动态：后端已移除硬编码假数据（2026-10-07），此处传空数组走真实空态
            renderActivities(data.dashboard ? data.dashboard.recent_activities : []);
        }
        loadStudents();
    } catch(e) {
        Object.values(statEls).forEach(el => { if (el) el.textContent = '-'; });
    }
}

function renderActivities(activities) {
    const list = document.getElementById('teacher-activity-list');
    if (!list) return;
    const rows = activities || [];
    // 平台目前没有真实的「最近动态」数据源（原接口返回的是硬编码假名字，已按
    // 「不编造」红线移除）。这里如实渲染空态，不留一张空白卡片。
    if (!rows.length) {
        list.innerHTML = '<div class="teacher-activity-empty">暂无动态</div>';
        return;
    }
    const icons = {
        student_join: { icon: 'fa-user-plus', color: '#4a6fa5' },
        certificate_earned: { icon: 'fa-award', color: '#1f5e43' },
        progress_update: { icon: 'fa-chart-line', color: '#d9a227' }
    };
    list.innerHTML = rows.map(a => {
        const cfg = icons[a.type] || { icon: 'fa-circle', color: '#94a3b8' };
        return `<div class="teacher-activity-item">
            <div class="teacher-activity-icon" style="color:${cfg.color}"><i class="fas ${cfg.icon}"></i></div>
            <div class="teacher-activity-info">
                <span class="teacher-activity-text">${a.student} — ${a.type === 'student_join' ? '加入学习' : a.type === 'certificate_earned' ? '获得证书' : '更新进度'}</span>
                <span class="teacher-activity-time">${a.time}</span>
            </div>
        </div>`;
    }).join('');
}

async function loadStudents(search = '') {
    const tbody = document.getElementById('teacher-student-tbody');
    if (!tbody) return;
    const countEl = document.getElementById('teacher-student-count');
    showSkeleton(tbody, 'row', 4);
    try {
        const endpoint = search ? `/api/teacher/students?search=${encodeURIComponent(search)}` : '/api/teacher/students';
        const data = await apiCall(endpoint);
        if (data.success) {
            if (countEl) countEl.textContent = `${data.students.length}人`;
            if (!data.students || data.students.length === 0) {
                showEmptyState(tbody, 'fa-users', '暂无学员', search ? '未找到匹配的学员' : '还没有添加学员');
                return;
            }
            tbody.innerHTML = data.students.map(s => `
                <tr>
                    <td><span class="teacher-student-id">${s.id}</span></td>
                    <td><span class="teacher-student-name">${escapeHtml(s.name)}</span></td>
                    <td><span class="teacher-direction-tag">${escapeHtml(s.direction || '未分类')}</span></td>
                    <td>
                        ${s.has_cert_data
                            ? `<div class="teacher-progress-cell">
                                    <div class="progress-bar small"><div class="progress-fill" style="width:${s.completion || 0}%"></div></div>
                                    <span class="teacher-progress-text">${s.completion || 0}%（证书${s.cert_earned || 0}/${s.cert_total || 0}）</span>
                                </div>`
                            : `<span class="teacher-progress-text">暂无证书记录${s.user_id ? '' : '（未关联账号）'}</span>`}
                    </td>
                    <td>${s.cert_earned > 0
                        ? '<span class="cert-badge">已获得</span>'
                        : '<span class="cert-badge pending">暂未获得</span>'}</td>
                    <td>${s.user_id
                        ? `<span class="cert-badge">已关联</span><div class="teacher-account-name">${escapeHtml(s.user_id)}</div>`
                        : `<span class="cert-badge pending">未关联</span><div class="teacher-account-name">无法登录</div>`}</td>
                    <td>
                        <div class="teacher-action-btns">
                            <button class="btn btn-text btn-sm view-student-btn" data-id="${s.id}" title="查看详情"><i class="fas fa-eye"></i></button>
                            <button class="btn btn-text btn-sm edit-student-btn" data-id="${s.id}" title="编辑"><i class="fas fa-pen"></i></button>
                            <button class="btn btn-text btn-sm delete-student-btn" data-id="${s.id}" data-name="${s.name}" title="删除"><i class="fas fa-trash-can"></i></button>
                        </div>
                    </td>
                </tr>
            `).join('');

            // 绑定查看按钮
            tbody.querySelectorAll('.view-student-btn').forEach(btn => {
                btn.addEventListener('click', () => openStudentDetail(btn.dataset.id));
            });
            // 绑定编辑按钮
            tbody.querySelectorAll('.edit-student-btn').forEach(btn => {
                btn.addEventListener('click', async () => {
                    try {
                        const d = await apiCall(`/api/teacher/students/${btn.dataset.id}`);
                        if (d.success) showEditStudentModal(d.student);
                    } catch(e) { showNotification('加载失败', 'error'); }
                });
            });
            // 绑定删除按钮
            tbody.querySelectorAll('.delete-student-btn').forEach(btn => {
                btn.addEventListener('click', () => confirmDeleteStudent(btn.dataset.id, btn.dataset.name));
            });
        }
    } catch(e) {
        if (tbody) showErrorState(tbody, '加载学员列表失败', () => loadStudents(search));
    }
}

async function openStudentDetail(studentId) {
    try {
        const d = await apiCall(`/api/teacher/students/${studentId}`);
        if (!d.success) { showNotification('加载失败', 'error'); return; }
        const st = d.student;
        // 口径：证书真实完成度（名册 progress 是手填字段，不再展示）
        const completion = st.completion || 0;
        const progressColor = completion >= 80 ? '#1f5e43' : completion >= 50 ? '#d9a227' : '#ef4444';
        showDetailModal(`学员详情`, `
            <div class="teacher-detail">
                <div class="teacher-detail-header">
                    <div class="teacher-detail-avatar">${escapeHtml((st.name || '?').charAt(0))}</div>
                    <div class="teacher-detail-info">
                        <div class="teacher-detail-name">${escapeHtml(st.name)}</div>
                        <div class="teacher-detail-id">${st.id} · ${escapeHtml(st.direction || '未分方向')}</div>
                    </div>
                    <span class="cert-badge ${st.cert_earned > 0 ? '' : 'pending'}">${st.cert_earned > 0 ? '已获得证书' : '暂未获得'}</span>
                </div>
                <div class="teacher-detail-stats">
                    <div class="teacher-detail-stat">
                        <span class="teacher-detail-stat-label">学习方向</span>
                        <span class="teacher-detail-stat-value">${escapeHtml(st.direction || '未分方向')}</span>
                    </div>
                    <div class="teacher-detail-stat">
                        <span class="teacher-detail-stat-label">完成度（证书）</span>
                        <span class="teacher-detail-stat-value" style="color:${progressColor}">${st.has_cert_data ? completion + '%（' + (st.cert_earned || 0) + '/' + (st.cert_total || 0) + '）' : '暂无记录'}</span>
                    </div>
                    <div class="teacher-detail-stat">
                        <span class="teacher-detail-stat-label">平台账号</span>
                        <span class="teacher-detail-stat-value">${st.user_id ? escapeHtml(st.user_id) : '未关联'}</span>
                    </div>
                    <div class="teacher-detail-stat">
                        <span class="teacher-detail-stat-label">状态</span>
                        <span class="teacher-detail-stat-value">${st.status === 'active' ? '在读' : escapeHtml(st.status || '')}</span>
                    </div>
                </div>
                ${st.has_cert_data ? `<div class="teacher-detail-progress-bar">
                    <div class="progress-bar"><div class="progress-fill" style="width:${completion}%; background:${progressColor}"></div></div>
                </div>` : ''}
                <div class="teacher-detail-actions">
                    <button class="btn btn-outline btn-sm" onclick="document.querySelector('.modal-overlay.detail-modal')?.remove(); setTimeout(() => openStudentDetail('${st.id}'), 200)">
                        <i class="fas fa-refresh"></i> 刷新
                    </button>
                    <button class="btn btn-primary btn-sm" id="detail-edit-btn">
                        <i class="fas fa-pen"></i> 编辑信息
                    </button>
                </div>
            </div>
        `);
        document.getElementById('detail-edit-btn')?.addEventListener('click', () => {
            document.querySelector('.modal-overlay.detail-modal')?.remove();
            setTimeout(() => showEditStudentModal(st), 200);
        });
    } catch(e) {
        showNotification('加载失败', 'error');
    }
}

function confirmDeleteStudent(studentId, studentName) {
    showDetailModal('确认删除', `
        <div class="teacher-confirm">
            <div class="teacher-confirm-icon"><i class="fas fa-triangle-exclamation"></i></div>
            <p class="teacher-confirm-text">确定要删除学员 <strong>${studentName}</strong> 吗？</p>
            <p class="teacher-confirm-hint">此操作不可撤销，该学员的所有学习记录将被删除。</p>
            <div class="teacher-confirm-actions">
                <button class="btn btn-outline" id="cancel-delete">取消</button>
                <button class="btn btn-danger" id="confirm-delete-btn">
                    <i class="fas fa-trash-can"></i> 确认删除
                </button>
            </div>
        </div>
    `);
    document.getElementById('cancel-delete')?.addEventListener('click', () => {
        document.querySelector('.modal-overlay.detail-modal')?.remove();
    });
    document.getElementById('confirm-delete-btn')?.addEventListener('click', async () => {
        try {
            const data = await apiCall(`/api/teacher/students/${studentId}`, 'DELETE');
            showNotification(data.message, data.success ? 'success' : 'error');
            if (data.success) {
                document.querySelector('.modal-overlay.detail-modal')?.remove();
                loadStudents();
                loadTeacherDashboard();
            }
        } catch(e) {
            showNotification('删除失败', 'error');
        }
    });
}

async function generateTeacherReport() {
    const textarea = document.getElementById('teacher-report-prompt');
    const prompt = textarea?.value.trim() || '';
    if (!prompt) {
        showNotification('请描述你想分析的内容', 'error');
        textarea?.focus();
        return;
    }

    // 打开弹窗并显示加载状态
    showDetailModal('AI 教学报告', `
        <div class="report-modal-body">
            <div class="report-loading">
                <div class="spinner"></div>
                <p>AI 正在分析学员数据并生成报告...</p>
                <span class="report-loading-hint">这可能需要几秒钟，请耐心等待</span>
            </div>
        </div>
    `, 'fa-wand-magic-sparkles');

    try {
        const data = await apiCall('/api/teacher/reports/generate', 'POST', { prompt });
        if (data.success) {
            const report = data.report;
            const ov = report.overview;
            const time = new Date(report.generated_at).toLocaleString('zh-CN');
            const body = document.querySelector('.modal-overlay.detail-modal .modal-body');
            if (!body) return;

            const sections = parseReportContent(report.content);

            // 根据 focus 构建不同的概览
            let overviewHtml = '';
            if (ov) {
                const focus = ov.focus || 'general';
                const allStats = {
                    total: { value: ov.total, label: '总学员', cls: '' },
                    avg_progress: { value: ov.avg_progress + '%', label: '平均完成度（证书）', cls: 'accent' },
                    direction_count: { value: ov.direction_count, label: '学习方向', cls: '' },
                    completed_count: { value: ov.completed_count, label: '已获证书', cls: 'success' },
                    excellent_count: { value: ov.excellent_count, label: '优秀学员', cls: 'warn' },
                    risk_count: { value: ov.risk_count, label: '风险学员', cls: 'danger' }
                };
                const hl = ov.highlight_stats || ['total', 'avg_progress', 'direction_count'];
                const statsHtml = hl.map(k => {
                    const s = allStats[k];
                    return s ? `<div class="report-stat-card ${s.cls}"><div class="report-stat-value">${s.value}</div><div class="report-stat-label">${s.label}</div></div>` : '';
                }).join('');

                // 主题特定的额外区块
                let extraHtml = '';

                if (focus === 'risk') {
                    // 风险主题：展开风险学员详情
                    if (ov.at_risk.length) {
                        extraHtml = `
                            <div class="report-overview-subtitle danger-text"><i class="fas fa-triangle-exclamation"></i> 风险学员（${ov.at_risk.length}人）</div>
                            <div class="report-risk-detail-list">
                                ${ov.at_risk.sort((a,b) => a.progress - b.progress).map(s => `
                                    <div class="report-risk-detail-item">
                                        <span class="report-risk-name">${s.name}</span>
                                        <span class="report-risk-dir">${s.direction}</span>
                                        <div class="report-risk-bar-track">
                                            <div class="report-risk-bar-fill" style="width:${s.progress}%;background:${s.progress < 15 ? '#ef4444' : '#d9a227'}"></div>
                                        </div>
                                        <span class="report-risk-pct">${s.progress}%</span>
                                    </div>
                                `).join('')}
                            </div>`;
                    } else {
                        extraHtml = '<div class="report-overview-ok"><i class="fas fa-circle-check"></i> 当前无风险学员，整体状况良好</div>';
                    }
                } else if (focus === 'direction') {
                    // 方向主题：按进度排序的方向对比
                    const sorted = [...ov.directions].sort((a, b) => b.avg_progress - a.avg_progress);
                    extraHtml = `
                        <div class="report-overview-subtitle"><i class="fas fa-ranking-star"></i> 方向排名</div>
                        <div class="report-dir-ranked">
                            ${sorted.map((d, i) => `
                                <div class="report-dir-ranked-item ${i === 0 ? 'first' : ''}">
                                    <span class="report-dir-rank">${i + 1}</span>
                                    <span class="report-dir-ranked-name">${d.name}</span>
                                    <span class="report-dir-ranked-count">${d.count}人</span>
                                    <div class="report-dir-bar-track">
                                        <div class="report-dir-bar-fill" style="width:${d.avg_progress}%"></div>
                                    </div>
                                    <span class="report-dir-progress">${d.avg_progress}%</span>
                                </div>
                            `).join('')}
                        </div>`;
                } else if (focus === 'progress') {
                    // 进度主题：展开进度分布
                    const maxBracket = Math.max(...Object.values(ov.brackets), 1);
                    extraHtml = `
                        <div class="report-overview-subtitle"><i class="fas fa-chart-bar"></i> 进度分布</div>
                        <div class="report-brackets">
                            ${Object.entries(ov.brackets).map(([k, v]) => `
                                <div class="report-bracket-item">
                                    <span class="report-bracket-label">${k}</span>
                                    <div class="report-bracket-track">
                                        <div class="report-bracket-fill" style="width:${(v / maxBracket * 100).toFixed(0)}%"></div>
                                    </div>
                                    <span class="report-bracket-value">${v}人</span>
                                </div>
                            `).join('')}
                        </div>`;
                } else if (focus === 'excellent') {
                    // 优秀主题：展开优秀学员
                    if (ov.excellent.length) {
                        extraHtml = `
                            <div class="report-overview-subtitle success-text"><i class="fas fa-star"></i> 优秀学员（${ov.excellent.length}人）</div>
                            <div class="report-risk-list">
                                ${ov.excellent.sort((a,b) => b.progress - a.progress).map(s => `
                                    <span class="report-excellent-tag">${s.name}<small>${s.direction} · ${s.progress}%</small></span>
                                `).join('')}
                            </div>`;
                    }
                } else if (focus === 'trend') {
                    // 趋势主题：完成率 + 风险率
                    const completionRate = ov.total ? (ov.completed_count / ov.total * 100).toFixed(1) : 0;
                    const riskRate = ov.total ? (ov.risk_count / ov.total * 100).toFixed(1) : 0;
                    extraHtml = `
                        <div class="report-overview-subtitle"><i class="fas fa-chart-line"></i> 关键指标</div>
                        <div class="report-trend-metrics">
                            <div class="report-trend-item">
                                <span class="report-trend-label">完成率</span>
                                <div class="report-trend-bar-track">
                                    <div class="report-trend-bar-fill success" style="width:${completionRate}%"></div>
                                </div>
                                <span class="report-trend-value">${completionRate}%</span>
                            </div>
                            <div class="report-trend-item">
                                <span class="report-trend-label">风险率</span>
                                <div class="report-trend-bar-track">
                                    <div class="report-trend-bar-fill danger" style="width:${riskRate}%"></div>
                                </div>
                                <span class="report-trend-value">${riskRate}%</span>
                            </div>
                        </div>`;
                } else if (focus === 'performance') {
                    // 教学主题：各方向完成率对比
                    const sorted = [...ov.directions].sort((a, b) => b.avg_progress - a.avg_progress);
                    extraHtml = `
                        <div class="report-overview-subtitle"><i class="fas fa-gauge-high"></i> 各方向教学完成度</div>
                        <div class="report-dir-list">
                            ${sorted.map(d => `
                                <div class="report-dir-item">
                                    <span class="report-dir-name">${d.name}</span>
                                    <span class="report-dir-count">${d.count}人</span>
                                    <div class="report-dir-bar-track">
                                        <div class="report-dir-bar-fill" style="width:${d.avg_progress}%"></div>
                                    </div>
                                    <span class="report-dir-progress">${d.avg_progress}%</span>
                                </div>
                            `).join('')}
                        </div>`;
                } else {
                    // 通用：简洁的方向 + 风险/优秀标签
                    const maxBracket = Math.max(...Object.values(ov.brackets), 1);
                    extraHtml = `
                        <div class="report-overview-subtitle">进度分布</div>
                        <div class="report-brackets">
                            ${Object.entries(ov.brackets).map(([k, v]) => `
                                <div class="report-bracket-item">
                                    <span class="report-bracket-label">${k}</span>
                                    <div class="report-bracket-track">
                                        <div class="report-bracket-fill" style="width:${(v / maxBracket * 100).toFixed(0)}%"></div>
                                    </div>
                                    <span class="report-bracket-value">${v}人</span>
                                </div>
                            `).join('')}
                        </div>
                        <div class="report-overview-subtitle">各方向概况</div>
                        <div class="report-dir-list">
                            ${ov.directions.map(d => `
                                <div class="report-dir-item">
                                    <span class="report-dir-name">${d.name}</span>
                                    <span class="report-dir-count">${d.count}人</span>
                                    <div class="report-dir-bar-track">
                                        <div class="report-dir-bar-fill" style="width:${d.avg_progress}%"></div>
                                    </div>
                                    <span class="report-dir-progress">${d.avg_progress}%</span>
                                </div>
                            `).join('')}
                        </div>
                        ${ov.at_risk.length ? `
                        <div class="report-overview-subtitle danger-text"><i class="fas fa-triangle-exclamation"></i> 需要关注的学员</div>
                        <div class="report-risk-list">
                            ${ov.at_risk.map(s => `<span class="report-risk-tag">${s.name}<small>${s.progress}%</small></span>`).join('')}
                        </div>` : ''}
                        ${ov.excellent.length ? `
                        <div class="report-overview-subtitle success-text"><i class="fas fa-star"></i> 优秀学员</div>
                        <div class="report-risk-list">
                            ${ov.excellent.map(s => `<span class="report-excellent-tag">${s.name}<small>${s.progress}%</small></span>`).join('')}
                        </div>` : ''}
                    `;
                }

                overviewHtml = `
                    <div class="report-overview report-focus-${focus}">
                        <div class="report-overview-title"><i class="fas fa-chart-pie"></i> ${ov.title || '数据概览'}</div>
                        <div class="report-stats-grid">
                            ${statsHtml}
                        </div>
                        ${extraHtml}
                    </div>
                `;
            }

            body.innerHTML = `
                <div class="report-modal">
                    <div class="report-meta">
                        <span class="report-meta-title">${report.title}</span>
                        <span class="report-meta-time"><i class="fas fa-clock"></i> ${time}</span>
                    </div>
                    ${overviewHtml}
                    <div class="report-toc">
                        <span class="report-toc-label">AI 分析</span>
                        ${sections.map((s, i) => `<a class="report-toc-item" href="#report-section-${i}">${s.title}</a>`).join('')}
                    </div>
                    <div class="report-sections">
                        ${sections.map((s, i) => `
                            <div class="report-section" id="report-section-${i}">
                                <h4 class="report-section-title">${s.title}</h4>
                                <div class="report-section-body">${s.body.replace(/\n/g, '<br>')}</div>
                            </div>
                        `).join('')}
                    </div>
                    <div class="report-footer">
                        <button class="btn btn-outline btn-sm" onclick="copyReportContent()"><i class="fas fa-copy"></i> 复制全文</button>
                    </div>
                </div>
            `;
        }
    } catch(e) {
        const body = document.querySelector('.modal-overlay.detail-modal .modal-body');
        if (body) {
            body.innerHTML = `
                <div class="report-error">
                    <i class="fas fa-circle-exclamation"></i>
                    <p>报告生成失败</p>
                    <span>请稍后重试</span>
                </div>
            `;
        }
    }
}

function parseReportContent(content) {
    // 按标题分割内容（支持 #、##、数字序号、中文序号）
    const lines = content.split('\n');
    const sections = [];
    let current = null;

    for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) {
            if (current) current.body += '\n';
            continue;
        }
        // 匹配标题行：# / ## / 一、二、 / 1. / 1、
        const isTitle = /^#{1,3}\s+/.test(trimmed)
            || /^[一二三四五六七八九十]+[、.．]/.test(trimmed)
            || /^\d+[、.．)\s]/.test(trimmed);

        if (isTitle) {
            const title = trimmed.replace(/^#+\s*/, '').replace(/^[一二三四五六七八九十]+[、.．]\s*/, '').replace(/^\d+[、.．)\s]*/, '');
            current = { title, body: '' };
            sections.push(current);
        } else if (current) {
            current.body += (current.body ? '\n' : '') + trimmed;
        } else {
            // 内容在第一个标题之前
            current = { title: '报告概览', body: trimmed };
            sections.push(current);
        }
    }
    return sections.filter(s => s.body.trim());
}

function copyReportContent() {
    const sections = document.querySelectorAll('.report-section-body');
    const text = Array.from(sections).map(s => s.innerText).join('\n\n');
    copyText(text, '报告内容已复制');
}

// ==================== 教师子标签 ====================

function setupTeacherTabs() {
    document.querySelectorAll('.teacher-tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const tab = btn.dataset.tab;
            // 切换按钮高亮
            document.querySelectorAll('.teacher-tab-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            // 切换面板
            document.querySelectorAll('.teacher-tab-panel').forEach(p => p.classList.remove('active'));
            const panel = document.getElementById('teacher-panel-' + tab);
            if (panel) panel.classList.add('active');
            // 按需加载数据
            if (tab === 'announcements') loadAnnouncements();
            else if (tab === 'analytics') loadAnalytics();
        });
    });
}

// ==================== 通知公告 ====================

async function loadAnnouncements() {
    const container = document.getElementById('teacher-announcements-list');
    if (!container) return;
    container.innerHTML = '<div class="teacher-loading"><div class="spinner"></div> 加载中...</div>';
    try {
        const data = await apiCall('/api/teacher/announcements');
        if (!data.success || !data.announcements.length) {
            container.innerHTML = '<div class="teacher-empty"><i class="fas fa-bullhorn"></i><p>暂无通知公告</p></div>';
            return;
        }
        container.innerHTML = data.announcements.map(a => `
            <div class="announcement-card ${a.pinned ? 'pinned' : ''}">
                <div class="announcement-header">
                    <span class="announcement-category cat-${a.category}">${a.category}</span>
                    ${a.pinned ? '<span class="announcement-pin"><i class="fas fa-thumbtack"></i> 置顶</span>' : ''}
                    <span class="announcement-time">${a.created_at}</span>
                </div>
                <h4 class="announcement-title">${a.title}</h4>
                <p class="announcement-content">${a.content}</p>
                <div class="announcement-actions">
                    <button class="btn btn-danger btn-xs" onclick="deleteAnnouncement(${a.id})"><i class="fas fa-trash"></i> 删除</button>
                </div>
            </div>
        `).join('');
    } catch(e) {
        container.innerHTML = '<div class="teacher-error">加载失败</div>';
    }
}

function showPublishAnnouncementModal() {
    showDetailModal('发布通知', `
        <div class="teacher-form">
            <div class="form-group">
                <label>标题</label>
                <input type="text" id="ann-title" placeholder="输入通知标题">
            </div>
            <div class="form-group">
                <label>分类</label>
                <select id="ann-category">
                    <option value="通知">通知</option>
                    <option value="公告">公告</option>
                    <option value="紧急">紧急</option>
                </select>
            </div>
            <div class="form-group">
                <label>内容</label>
                <textarea id="ann-content" rows="5" placeholder="输入通知内容"></textarea>
            </div>
            <div class="form-group">
                <label class="checkbox-label">
                    <input type="checkbox" id="ann-pinned"> 置顶显示
                </label>
            </div>
            <button class="btn btn-primary teacher-form-submit" id="submit-announcement">
                <i class="fas fa-paper-plane"></i> 发布
            </button>
        </div>
    `);
    document.getElementById('submit-announcement')?.addEventListener('click', async () => {
        const title = document.getElementById('ann-title').value.trim();
        const content = document.getElementById('ann-content').value.trim();
        const category = document.getElementById('ann-category').value;
        const pinned = document.getElementById('ann-pinned').checked ? 1 : 0;
        if (!title || !content) { showNotification('请填写标题和内容', 'error'); return; }
        try {
            const data = await apiCall('/api/teacher/announcements', 'POST', { title, content, category, pinned });
            showNotification(data.message, data.success ? 'success' : 'error');
            if (data.success) {
                document.querySelector('.modal-overlay.detail-modal')?.remove();
                loadAnnouncements();
            }
        } catch(e) {
            showNotification('发布失败', 'error');
        }
    });
}

async function deleteAnnouncement(id) {
    if (!confirm('确定删除此通知？')) return;
    try {
        const data = await apiCall('/api/teacher/announcements/' + id, 'DELETE');
        showNotification(data.message, data.success ? 'success' : 'error');
        if (data.success) loadAnnouncements();
    } catch(e) {
        showNotification('删除失败', 'error');
    }
}

// ==================== 学情分析 ====================

async function loadAnalytics() {
    const container = document.getElementById('teacher-analytics-content');
    if (!container) return;
    container.innerHTML = '<div class="teacher-loading"><div class="spinner"></div> 加载中...</div>';
    try {
        const data = await apiCall('/api/teacher/analytics');
        if (!data.success) throw new Error();
        const a = data.analytics || {};
        container.innerHTML = `
            ${a.no_cert_count > 0
                ? `<div class="teacher-form-hint" style="margin-bottom:10px">口径：${escapeHtml(a.basis_label || '证书真实完成度')}。另有 <b>${a.no_cert_count}</b> 名学员暂无任何证书记录，未计入分布（不等于 0% 完成）。</div>`
                : (a.basis_label ? `<div class="teacher-form-hint" style="margin-bottom:10px">口径：${escapeHtml(a.basis_label)}</div>` : '')}
            <div class="analytics-section">
                <h4 class="analytics-section-title"><i class="fas fa-chart-bar"></i> 完成度分布</h4>
                <div class="analytics-chart" id="progress-chart"></div>
            </div>
            <div class="analytics-section">
                <h4 class="analytics-section-title"><i class="fas fa-chart-pie"></i> 方向分布</h4>
                <div class="analytics-chart" id="direction-chart"></div>
            </div>
            <div class="analytics-section">
                <h4 class="analytics-section-title"><i class="fas fa-table"></i> 各方向完成度详情</h4>
                <div id="direction-detail"></div>
            </div>
        `;
        renderProgressChart(a.progress_distribution || []);
        renderDirectionChart(a.direction_distribution || []);
        renderDirectionDetail(a.direction_progress || []);
    } catch(e) {
        container.innerHTML = '<div class="teacher-error">学情数据加载失败，请刷新重试</div>';
    }
}

function renderProgressChart(dist) {
    const el = document.getElementById('progress-chart');
    if (!el || !dist.length) { if (el) el.innerHTML = '<p class="text-muted">暂无数据</p>'; return; }
    const max = Math.max(...dist.map(d => d.count), 1);
    el.innerHTML = `
        <div class="bar-chart">
            ${dist.map(d => `
                <div class="bar-item">
                    <div class="bar-label">${d.label || d.range || ''}</div>
                    <div class="bar-track">
                        <div class="bar-fill" style="width:${(d.count / max * 100).toFixed(1)}%"></div>
                    </div>
                    <div class="bar-value">${d.count}人</div>
                </div>
            `).join('')}
        </div>
    `;
}

function renderDirectionChart(dist) {
    const el = document.getElementById('direction-chart');
    if (!el || !dist.length) { if (el) el.innerHTML = '<p class="text-muted">暂无数据</p>'; return; }
    const total = dist.reduce((s, d) => s + d.count, 0) || 1;
    const colors = ['#1f5e43','#4a6fa5','#d9a227','#4a8a6a','#a9673a','#8fc0a5'];
    el.innerHTML = `
        <div class="pie-list">
            ${dist.map((d, i) => `
                <div class="pie-item">
                    <span class="pie-dot" style="background:${colors[i % colors.length]}"></span>
                    <span class="pie-label">${d.direction}</span>
                    <span class="pie-value">${d.count}人 (${(d.count / total * 100).toFixed(1)}%)</span>
                    <div class="pie-bar-track">
                        <div class="pie-bar-fill" style="width:${(d.count / total * 100).toFixed(1)}%;background:${colors[i % colors.length]}"></div>
                    </div>
                </div>
            `).join('')}
        </div>
    `;
}

function renderDirectionDetail(data) {
    const el = document.getElementById('direction-detail');
    if (!el || !data.length) { if (el) el.innerHTML = '<p class="text-muted">暂无数据</p>'; return; }
    // ⚠️ 只渲染后端真的下发了字段：此前这里写死「学员数 / 平均进度 / 平均成绩」三列，
    //    但接口从不下发 student_count / avg_score，表格里一直是两列 undefined。
    //    平均成绩没有真实数据来源，按「宁缺勿编」直接不渲染这一列。
    el.innerHTML = `
        <table class="teacher-table">
            <thead><tr><th>方向</th><th>学员数</th><th>平均完成度</th><th>已获证书</th></tr></thead>
            <tbody>
                ${data.map(d => `<tr>
                    <td>${escapeHtml(d.direction || '未分类')}</td>
                    <td>${d.student_count ?? '-'}</td>
                    <td>${d.avg_progress != null ? Number(d.avg_progress).toFixed(1) + '%' : '-'}</td>
                    <td>${d.cert_earned ?? '-'}</td>
                </tr>`).join('')}
            </tbody>
        </table>
    `;
}

// ==================== 3D播放控制 ====================
// 非遗板块「3D互动教学」——把教师上传的已发布模型（models_3d 表 + public-models-3d 接口）
// 接到 model-viewer 上真实渲染，三个按钮从假提示改为真功能。

// 3D 播放器状态
const Craft3DState = {
    models: [],          // 当前手工艺的已发布模型列表
    activeIndex: -1,     // 当前展示的模型下标
    paused: false,       // 是否暂停自动旋转
    slow: false,         // 是否慢放
    angleStep: 0,        // 多角度切换步进（0 正面 / 1 侧面 / 2 顶部 / 3 特写）
};

// 多角度预设：orbit 的 theta（绕 Y 轴水平角）+ phi（俯仰角）+ 距离
const CRAFT_ANGLES = [
    { label: '正面', theta: '0deg', phi: '75deg', radius: 'auto' },
    { label: '侧面', theta: '90deg', phi: '75deg', radius: 'auto' },
    { label: '顶部', theta: '0deg', phi: '15deg', radius: 'auto' },
    { label: '特写', theta: '0deg', phi: '75deg', radius: '1.5m' },
];

function setup3DControls() {
    // 三个播放控制按钮 → 真功能
    document.getElementById('slow-play')?.addEventListener('click', () => toggleSlowPlay());
    document.getElementById('pause-play')?.addEventListener('click', () => togglePausePlay());
    document.getElementById('multi-angle')?.addEventListener('click', () => cycleAngle());
    // ④ AR 实景查看（移动端增值点）
    document.getElementById('ar-view')?.addEventListener('click', () => activateCraftAR());
    // 初始化时载入默认手工艺（刺绣）的模型
    loadCraftModels();
}

// 无模型 / 加载中时禁用四个播放控制按钮，并给出原因（P2-B：不再点了没反应）
function set3DControlsEnabled(enabled, reason) {
    ['slow-play', 'pause-play', 'multi-angle', 'ar-view'].forEach(id => {
        const btn = document.getElementById(id);
        if (!btn) return;
        btn.disabled = !enabled;
        if (enabled) {
            btn.removeAttribute('title');
        } else {
            btn.title = reason || '请先加载 3D 模型';
        }
    });
}

function getCraftViewer() {
    return document.getElementById('craft-3d-viewer');
}

function getCraftPlaceholder() {
    return document.getElementById('craft-3d-placeholder');
}

function getCraftStatus() {
    return document.getElementById('craft-3d-status');
}

// 载入当前手工艺的已发布 3D 模型（切手工艺时调用）
async function loadCraftModels() {
    const craft = AppState.currentCraft || 'embroidery';
    const viewer = getCraftViewer();
    const ph = getCraftPlaceholder();
    const status = getCraftStatus();
    const tabs = document.getElementById('craft-model-tabs');
    if (!viewer || !ph) return;

    Craft3DState.models = [];
    Craft3DState.activeIndex = -1;
    if (tabs) tabs.innerHTML = '';
    // P1/P2（2026-10-06 学员走查）：切手工艺时复位所有播放控制状态，
    // 避免「暂停/慢放」跨模型残留；同时禁用播放按钮，防止加载期间留下脏状态。
    resetCraftPlayState();
    set3DLoading(true, '3D模型加载中...');

    try {
        const data = await apiCall(`/api/teacher/public-models-3d?craft_type=${encodeURIComponent(craft)}`);
        const models = (data && data.models) || [];
        if (!models.length) {
            set3DLoading(false, null);
            show3DEmpty('该手工艺暂无可展示的 3D 模型，教师可在后台上传');
            return;
        }
        Craft3DState.models = models;
        // 渲染切换标签（多于 1 个模型时展示）
        if (tabs && models.length > 1) {
            tabs.innerHTML = models.map((m, i) =>
                `<button class="craft-model-tab${i === 0 ? ' active' : ''}" data-i="${i}">${escapeHtml(m.title || ('模型' + (i + 1)))}</button>`
            ).join('');
            tabs.querySelectorAll('.craft-model-tab').forEach(btn => {
                btn.addEventListener('click', () => {
                    const i = parseInt(btn.dataset.i, 10);
                    showCraftModel(i);
                    tabs.querySelectorAll('.craft-model-tab').forEach(b => b.classList.remove('active'));
                    btn.classList.add('active');
                });
            });
        }
        showCraftModel(0);
    } catch (e) {
        // 失败必须可见：不冒充「没有模型」，明确提示加载失败可重试
        set3DLoading(false, null);
        show3DEmpty('3D 模型加载失败，请稍后重试');
        console.error('loadCraftModels failed:', e);
    }
}

// 展示指定下标模型
function showCraftModel(index) {
    const viewer = getCraftViewer();
    const ph = getCraftPlaceholder();
    const m = Craft3DState.models[index];
    if (!m || !viewer || !ph) return;
    Craft3DState.activeIndex = index;

    // 构造模型文件 URL：file_path 形如 uploads/models_3d/xxx.glb，静态服务已放行该目录与后缀
    const url = (m.file_path || '').replace(/\\/g, '/');
    viewer.src = url;
    viewer.alt = m.title || '';
    // 重置视角与控制状态（每次展示新模型都从「正面 + 自动旋转」的干净态开始）
    viewer.setAttribute('camera-orbit', '0deg 75deg auto');
    viewer.setAttribute('field-of-view', 'auto');
    Craft3DState.angleStep = 0;
    resetCraftPlayState();

    viewer.classList.remove('is-hidden');
    ph.classList.add('is-hidden');
    set3DControlsEnabled(true);
    // 同步按钮状态（复位后 paused/slow 均为 false，恢复正常旋转 + 按钮取消激活）
    applyPlayControls();
}

// 空状态：无模型 / 加载失败
function show3DEmpty(msg) {
    const ph = getCraftPlaceholder();
    const status = getCraftStatus();
    const viewer = getCraftViewer();
    set3DControlsEnabled(false, msg || '暂无 3D 模型');
    if (viewer) viewer.classList.add('is-hidden');
    if (ph) ph.classList.remove('is-hidden');
    if (ph) {
        const icon = ph.querySelector('i');
        if (icon) {
            icon.className = 'fas fa-exclamation-circle';
        }
    }
    if (status) status.textContent = msg || '暂无 3D 模型';
}

// 加载中 / 恢复占位
function set3DLoading(loading, msg) {
    const ph = getCraftPlaceholder();
    const status = getCraftStatus();
    const viewer = getCraftViewer();
    if (loading) {
        set3DControlsEnabled(false, msg || '3D 模型加载中，请稍候');
        if (viewer) viewer.classList.add('is-hidden');
        if (ph) ph.classList.remove('is-hidden');
        if (ph) {
            const icon = ph.querySelector('i');
            if (icon) icon.className = 'fas fa-cube';
        }
        if (status) status.textContent = msg || '3D模型加载中...';
    }
}

// 复位播放控制状态（paused/slow/angleStep），并取消按钮激活态。
// P1/P2：切手工艺、展示新模型时调用，避免状态跨模型残留。
function resetCraftPlayState() {
    Craft3DState.paused = false;
    Craft3DState.slow = false;
    Craft3DState.angleStep = 0;
    const slowBtn = document.getElementById('slow-play');
    const pauseBtn = document.getElementById('pause-play');
    if (slowBtn) slowBtn.classList.remove('active');
    if (pauseBtn) pauseBtn.classList.remove('active');
}

// 慢放开关：rotation-per-second 从 30deg 降到 10deg
function toggleSlowPlay() {
    const viewer = getCraftViewer();
    if (!viewer || Craft3DState.activeIndex < 0) return; // P2：无模型时不响应，避免脏状态
    Craft3DState.slow = !Craft3DState.slow;
    applyPlayControls();
    showNotification(Craft3DState.slow ? '已切换慢放模式' : '已恢复正常速度', 'info');
}

// 暂停开关：停止自动旋转（auto-rotate 属性）
function togglePausePlay() {
    const viewer = getCraftViewer();
    if (!viewer || Craft3DState.activeIndex < 0) return; // P2：无模型时不响应
    Craft3DState.paused = !Craft3DState.paused;
    applyPlayControls();
    showNotification(Craft3DState.paused ? '已暂停自动旋转' : '已恢复自动旋转', 'info');
}

// 多角度：循环切换 4 个预设视角
function cycleAngle() {
    const viewer = getCraftViewer();
    if (!viewer || Craft3DState.activeIndex < 0) return;
    Craft3DState.angleStep = (Craft3DState.angleStep + 1) % CRAFT_ANGLES.length;
    const a = CRAFT_ANGLES[Craft3DState.angleStep];
    viewer.setAttribute('camera-orbit', `${a.theta} ${a.phi} ${a.radius}`);
    if (a.radius !== 'auto') {
        viewer.setAttribute('field-of-view', '35deg');
    } else {
        viewer.setAttribute('field-of-view', 'auto');
    }
    showNotification(`已切换到${a.label}视角`, 'info');
}

// ④ AR 实景查看：调用 model-viewer 的 activateAR，把模型「放到现实空间」。
// 仅支持移动端（iOS Quick Look / Android Scene Viewer）；桌面端给友好提示。
async function activateCraftAR() {
    const viewer = getCraftViewer();
    if (!viewer || Craft3DState.activeIndex < 0) return;
    if (typeof viewer.activateAR !== 'function') {
        showNotification('当前设备或浏览器不支持 AR 实景查看', 'warning');
        return;
    }
    try {
        await viewer.activateAR();
    } catch (e) {
        // AR 启动失败（桌面端、无相机权限等）给明确提示，不静默
        showNotification('AR 启动失败：请在手机端打开本页面重试', 'warning');
        console.warn('activateAR failed:', e);
    }
}

// 统一把状态写到 model-viewer 属性 + 同步按钮激活态
function applyPlayControls() {
    const viewer = getCraftViewer();
    if (!viewer) return;
    if (Craft3DState.paused) {
        viewer.removeAttribute('auto-rotate');
    } else {
        viewer.setAttribute('auto-rotate', '');
        viewer.setAttribute('rotation-per-second', Craft3DState.slow ? '10deg' : '30deg');
    }
    // 按钮激活态
    const slowBtn = document.getElementById('slow-play');
    const pauseBtn = document.getElementById('pause-play');
    if (slowBtn) slowBtn.classList.toggle('active', Craft3DState.slow);
    if (pauseBtn) pauseBtn.classList.toggle('active', Craft3DState.paused);
}

// 步骤 → 视角联动（2026-10-06）：点击制作步骤时，把 3D 视口切到对应视角。
// 按「步骤序号在总步数中的位置」映射到四个预设视角：
//   起步步骤 → 整体正面；中段步骤 → 侧面/特写；末段步骤 → 成品顶部。
// 这样四个手工艺（步骤数不同）都能通用，无需为每个步骤硬编码视角。
function focusCraftStep(stepIndex, totalSteps) {
    const viewer = getCraftViewer();
    if (!viewer || Craft3DState.activeIndex < 0) return; // 无模型时不联动

    // 计算进度（0~1）
    const progress = totalSteps > 1 ? stepIndex / (totalSteps - 1) : 0;
    let orbit, fov = 'auto';
    if (progress < 0.25) {
        orbit = '0deg 75deg auto';      // 起步：正面整体
    } else if (progress < 0.6) {
        orbit = '90deg 60deg auto';     // 中段：侧面观察细节
    } else if (progress < 0.85) {
        orbit = '45deg 45deg 1.8m';     // 后段：斜上方特写
        fov = '40deg';
    } else {
        orbit = '0deg 15deg auto';      // 末段：成品顶部俯视
    }
    viewer.setAttribute('camera-orbit', orbit);
    viewer.setAttribute('field-of-view', fov);
}

// ==================== 消息通知 ====================

// 当前登录学员的真实 user_id（username）。严禁再用 AppState.currentUser（全站从未赋值，
// 会退化成 sessionId 这个 UUID，导致按 user_id 查不到任何数据 → 消息中心对谁都不可见）。
function currentUserId() {
    return AppState.user?.id || '';
}

function setupQuickMessage() {
    const btn = document.getElementById('quick-message-btn');
    const dropdown = document.getElementById('msg-dropdown');
    if (!btn || !dropdown) return;

    // 铃铛点击切换下拉面板
    btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const isOpen = dropdown.classList.toggle('show');
        if (isOpen) {
            updateBadgeCount();
            loadNotifications();
            loadConversations();
        }
    });

    // 点击外部关闭
    document.addEventListener('click', (e) => {
        if (!dropdown.contains(e.target) && e.target !== btn) {
            dropdown.classList.remove('show');
        }
    });

    // 阻止面板内部点击冒泡
    dropdown.addEventListener('click', (e) => e.stopPropagation());

    // 标签切换
    dropdown.querySelectorAll('.msg-tab-btn').forEach(tabBtn => {
        tabBtn.addEventListener('click', () => {
            dropdown.querySelectorAll('.msg-tab-btn').forEach(b => b.classList.remove('active'));
            tabBtn.classList.add('active');
            const tab = tabBtn.dataset.tab;
            document.getElementById('msg-notifications-list').classList.toggle('is-hidden', tab !== 'notifications');
            document.getElementById('msg-messages-list').classList.toggle('is-hidden', tab !== 'messages');
        });
    });

    // 全部已读
    document.getElementById('msg-mark-all-read')?.addEventListener('click', markAllNotificationsRead);

    // 清除已读
    document.getElementById('msg-clear-read')?.addEventListener('click', clearReadNotifications);

    // 写消息
    document.getElementById('msg-compose-btn')?.addEventListener('click', showComposeModal);

    // 初始加载badge
    updateBadgeCount();
}

async function updateBadgeCount() {
    const badge = document.getElementById('message-badge');
    if (!badge) return;
    // 用户关闭了消息通知 → 不拉取、不显示红点
    if (!isNotifEnabled()) { badge.classList.add('is-hidden'); return; }
    try {
        const userId = currentUserId();
        if (!userId) return;
        const [notifRes, msgRes] = await Promise.all([
            apiCall(`/api/notifications/unread?user_id=${userId}`),
            apiCall(`/api/messages/unread?user_id=${userId}`)
        ]);
        const total = (notifRes.count || 0) + (msgRes.count || 0);
        badge.textContent = total;
        badge.classList.toggle('is-hidden', total === 0);
    } catch(e) { console.warn('[消息中心] 未读红点加载失败', e); }
}

// ==================== 未读红点 · 实时刷新 ====================
// 红点原仅「登录 / 刷新页面 / 自己发消息后」计算一次 → 对方（企业/教师）在
// 另一个窗口发来新消息时，本端页面即使一直开着，铃铛红点也永远不更新，
// 表现为「消息中心能看到新消息，但铃铛没有红色数字」（2026-10-09 修）。
// 补三条刷新通道：① 打开消息中心时 ② 窗口重获焦点 / 切回前台时 ③ 定时轮询（仅已登录且页面可见）。
let badgePollTimer = null;
const BADGE_POLL_MS = 15000;
function startBadgePolling() {
    if (badgePollTimer) return;
    badgePollTimer = setInterval(() => {
        if (AppState.user && document.visibilityState === 'visible') updateBadgeCount();
    }, BADGE_POLL_MS);
}
function stopBadgePolling() {
    if (badgePollTimer) { clearInterval(badgePollTimer); badgePollTimer = null; }
}
// 窗口重获焦点 / 从后台切回前台 → 立即刷新一次（比等下一次轮询更即时）
window.addEventListener('focus', () => { if (AppState.user) updateBadgeCount(); });
document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible' && AppState.user) updateBadgeCount();
});

// ==================== 会话内消息 · 实时刷新 ====================
// 原 bug：打开会话后页面停在聊天窗口，对方（学员/企业/教师）发来新消息不会自动出现，
// 必须手动刷新才能看到（2026-10-09 修）。修法：会话打开期间每 4 秒拉一次会话，
// 只把「本地还没有」的新消息追加进气泡区；会话弹窗关闭（#conversation-messages 被移除）即自动停。
let convPollTimer = null;
let convPollTarget = null;
const CONV_POLL_MS = 4000;
function startConvPolling(userId) {
    convPollTarget = userId;
    if (convPollTimer) return;
    convPollTimer = setInterval(convTick, CONV_POLL_MS);
    convTick();
}
function stopConvPolling() {
    convPollTarget = null;
    if (convPollTimer) { clearInterval(convPollTimer); convPollTimer = null; }
}
async function convTick() {
    const box = document.getElementById('conversation-messages');
    if (!box) { stopConvPolling(); return; }                       // 弹窗已关闭 → 停轮询
    if (!AppState.user || document.visibilityState !== 'visible') return;
    const myId = currentUserId();
    if (!myId || !convPollTarget) return;
    try {
        const data = await apiCall(`/api/messages/conversation/${convPollTarget}?user_id=${myId}`);
        if (!data.success || !data.messages) return;
        appendConvMessages(box, data.messages, myId);
    } catch (e) { /* 静默，下次轮询再试 */ }
}
// 会话消息唯一键：messages.id 既有整数（早期种子行）又有 UUID 字符串，
// 直接比较会因 "7" !== 7 而误判为「新消息」造成重复气泡 —— 统一转字符串。
// 极端情况下 id 为空则退化为「发送者|时间|内容」组合键，仍可去重。
function convMidOf(m) {
    if (!m) return '';
    if (m.id !== null && m.id !== undefined) return 'i' + m.id;
    return 'c' + (m.sender_id || '') + '|' + (m.created_at || '') + '|' + (m.content || '');
}
function appendConvMessages(box, messages, myId) {
    const existing = new Set();
    box.querySelectorAll('.msg-bubble').forEach(b => { if (b.dataset.mid) existing.add(String(b.dataset.mid)); });
    let emptyEl = box.querySelector('.msg-empty');
    const nearBottom = (box.scrollHeight - box.scrollTop - box.clientHeight) < 80;  // 仅当用户停在底部时才自动滚到底
    let appended = false;
    messages.forEach(m => {
        const mid = convMidOf(m);
        if (mid && existing.has(mid)) return;                     // 去重：跳过已渲染的（含本地刚发出的）
        if (emptyEl) { emptyEl.remove(); emptyEl = null; }
        const bubble = document.createElement('div');
        bubble.className = 'msg-bubble ' + (m.sender_id === myId ? 'mine' : 'theirs');
        if (mid) bubble.dataset.mid = mid;
        bubble.innerHTML = `<div class="msg-bubble-content">${escapeHtml(m.content || '')}</div>`
            + `<div class="msg-bubble-time">${m.created_at ? escapeHtml(m.created_at.slice(11, 16)) : ''}</div>`;
        box.appendChild(bubble);
        appended = true;
    });
    if (appended && nearBottom) box.scrollTop = box.scrollHeight;
}

async function loadNotifications() {
    const container = document.getElementById('msg-notifications-list');
    if (!container) return;
    const uid = currentUserId();
    if (!uid) { container.innerHTML = '<div class="msg-empty"><i class="fas fa-user-lock"></i><p>登录后可查看通知</p><button type="button" class="btn btn-text btn-sm" data-login-cta="1">去登录</button></div>'; bindLoginCta(container); return; }
    if (!isNotifEnabled()) {
        container.innerHTML = '<div class="msg-empty"><i class="fas fa-bell-slash"></i><p>消息通知已关闭</p><button type="button" class="btn btn-text btn-sm" id="msg-notif-enable">开启通知</button></div>';
        const eb = document.getElementById('msg-notif-enable');
        if (eb) eb.addEventListener('click', () => { setNotifEnabled(true); loadNotifications(); updateBadgeCount(); });
        return;
    }
    container.innerHTML = '<div class="msg-empty"><i class="fas fa-spinner fa-spin"></i><p>加载中...</p></div>';

    const items = [];
    let srcFailed = 0;
    // 1. 管理员系统公告（只读）
    try {
        const r = await apiCall('/api/system-announcements');
        (r.announcements || []).forEach(a => items.push({
            type: 'announcement', tag: '系统公告', readOnly: true,
            title: a.title || '系统公告',
            preview: a.content || '',
            time: a.created_at || '',
            ts: new Date((a.created_at || '').replace(' ', 'T')).getTime() || 0
        }));
    } catch (e) { srcFailed++; console.warn('[消息中心] 系统公告加载失败', e); }

    // 2. 企业端就业对接（投递状态，可回复企业）
    try {
        const r = await apiCall(`/api/employment/my-jobs/${uid}`);
        // interview 是后端白名单里的第四种状态，缺了就会把英文原文显示给学员（2026-10-09）
        const statusMap = { pending: '待处理', interview: '已通知面试', approved: '已通过', rejected: '未通过' };
        (r.applications || []).forEach(a => items.push({
            type: 'job', tag: '企业通知',
            replyId: a.enterprise_id || '', replyName: a.company || '企业',
            title: `投递「${a.title || '岗位'}」`,
            preview: `状态：${statusMap[a.status] || a.status}　${a.company || ''}　${a.location || ''}`,
            time: a.applied_at || '',
            ts: new Date((a.applied_at || '').replace(' ', 'T')).getTime() || 0
        }));
    } catch (e) { srcFailed++; console.warn('[消息中心] 投递状态加载失败', e); }

    // 3. 教师/企业互动私信（对方发来的，可回复）
    try {
        const r = await apiCall(`/api/messages/inbox?user_id=${uid}`);
        (r.inbox || []).forEach(m => {
            if (m.is_mine) return;
            items.push({
                type: 'interaction', tag: '互动',
                replyId: m.other_id || '', replyName: m.other_name || '对方',
                title: `来自 ${m.other_name || '对方'} 的消息`,
                preview: m.content || '',
                time: m.created_at || '',
                ts: new Date((m.created_at || '').replace(' ', 'T')).getTime() || 0
            });
        });
    } catch (e) { srcFailed++; console.warn('[消息中心] 互动私信加载失败', e); }

    // 4. 平台站内通知（教师公告推送 / 实训批改等，按 username 定向写入 notifications 表）
    // 2026-10-07 补：notifications 表此前对前端是「只写不读」——
    // updateBadgeCount 会把未读数算进红点，但列表里看不到任何对应条目（红点有数字却点不出东西）。
    // 这里接上第 4 个数据源，让红点数与列表内容对得上。
    // 2026-10-07 再修：「发布作业」下架后，站内通知只剩 announcement / grade / farming_reminder，
    //   已无 type='assignment' 的通知，故从两张映射表里删掉该分支（保留只会误导）。
    try {
        const r = await apiCall(`/api/notifications?user_id=${uid}`);
        const notifTagMap = { announcement: '公告', grade: '实训批改' };
        (r.notifications || []).forEach(n => items.push({
            type: n.type || 'system', tag: notifTagMap[n.type] || '通知', readOnly: true,
            title: n.title || '通知',
            preview: n.content || '',
            time: n.created_at || '',
            ts: new Date((n.created_at || '').replace(' ', 'T')).getTime() || 0
        }));
    } catch (e) { srcFailed++; console.warn('[消息中心] 站内通知加载失败', e); }

    if (!items.length) {
        if (srcFailed >= 4) {
            container.innerHTML = '<div class="msg-empty"><i class="fas fa-exclamation-triangle"></i><p>通知加载失败</p><button type="button" class="btn btn-text btn-sm" id="msg-notif-retry">重试</button></div>';
            const rb = document.getElementById('msg-notif-retry');
            if (rb) rb.addEventListener('click', loadNotifications);
            return;
        }
        container.innerHTML = '<div class="msg-empty"><i class="fas fa-bell-slash"></i><p>暂无通知</p></div>';
        return;
    }
    items.sort((a, b) => b.ts - a.ts);
    const iconMap = { announcement: 'fa-bullhorn', job: 'fa-briefcase', interaction: 'fa-comments',
                      grade: 'fa-check-circle', system: 'fa-bell' };
    container.innerHTML = items.map(it => `
        <div class="msg-item ${it.replyId ? 'has-reply' : ''}">
            <div class="msg-item-icon type-${it.type}"><i class="fas ${iconMap[it.type] || 'fa-bell'}"></i></div>
            <div class="msg-item-text">
                <div class="msg-item-title">${escapeHtml(it.title)} <span class="msg-tag msg-tag-${it.type}">${it.tag}</span></div>
                <div class="msg-item-preview">${escapeHtml(it.preview)}</div>
                <div class="msg-item-time">${formatTimeAgo(it.time)}</div>
                ${it.replyId ? `<button class="msg-reply-btn" data-rid="${escapeHtml(it.replyId)}" data-rname="${escapeHtml(it.replyName || '')}">回复</button>` : ''}
            </div>
        </div>
    `).join('');
    container.querySelectorAll('.msg-reply-btn').forEach(btn => {
        btn.addEventListener('click', () => openConversation(btn.dataset.rid, btn.dataset.rname));
    });
}

async function loadConversations() {
    const container = document.getElementById('msg-messages-list');
    if (!container) return;
    const userId = currentUserId();
    if (!userId) { container.innerHTML = '<div class="msg-empty"><i class="fas fa-user-lock"></i><p>登录后可查看私信</p><button type="button" class="btn btn-text btn-sm" data-login-cta="1">去登录</button></div>'; bindLoginCta(container); return; }
    try {
        const data = await apiCall(`/api/messages/inbox?user_id=${userId}`);
        if (!data.success || !data.inbox.length) {
            container.innerHTML = '<div class="msg-empty"><i class="fas fa-envelope-open"></i><p>暂无私信</p></div>';
            return;
        }
        container.innerHTML = data.inbox.map(m => {
            const time = formatTimeAgo(m.created_at);
            const preview = m.is_mine ? `我：${m.content}` : m.content;
            return `
                <div class="msg-item ${m.is_read || m.is_mine ? '' : 'unread'}" onclick="openConversation('${m.other_id}', '${m.other_name}')">
                    <div class="msg-item-avatar"><i class="fas fa-user"></i></div>
                    <div class="msg-item-text">
                        <div class="msg-item-title">${m.other_name}</div>
                        <div class="msg-item-preview">${preview}</div>
                        <div class="msg-item-time">${time}</div>
                    </div>
                </div>
            `;
        }).join('');
    } catch(e) {
        container.innerHTML = '<div class="msg-empty">加载失败</div>';
    }
}

function formatTimeAgo(dateStr) {
    if (!dateStr) return '';
    const date = new Date(dateStr.replace(' ', 'T'));
    const now = new Date();
    const diff = (now - date) / 1000;
    if (diff < 60) return '刚刚';
    if (diff < 3600) return Math.floor(diff / 60) + '分钟前';
    if (diff < 86400) return Math.floor(diff / 3600) + '小时前';
    if (diff < 604800) return Math.floor(diff / 86400) + '天前';
    return dateStr.slice(0, 10);
}

async function openConversation(userId, userName) {
    // 关闭下拉面板
    document.getElementById('msg-dropdown')?.classList.remove('show');

    const myId = currentUserId();
    if (!myId) return;

    // 加载会话消息
    let messages = [];
    let convFailed = false;
    try {
        const data = await apiCall(`/api/messages/conversation/${userId}?user_id=${myId}`);
        if (data.success) messages = data.messages;
        else convFailed = true;
    } catch(e) { convFailed = true; console.warn('[消息中心] 会话历史加载失败', e); }

    showDetailModal(`与 ${userName} 的对话`, `
        <div class="conversation-modal">
            <div class="conversation-messages" id="conversation-messages">
                ${convFailed
                    ? '<div class="msg-empty"><i class="fas fa-triangle-exclamation"></i><p>历史消息加载失败</p></div>'
                    : (messages.length
                        ? messages.map(m => `
                    <div class="msg-bubble ${m.sender_id === myId ? 'mine' : 'theirs'}" data-mid="${convMidOf(m)}">
                        <div class="msg-bubble-content">${escapeHtml(m.content || '')}</div>
                        <div class="msg-bubble-time">${m.created_at ? escapeHtml(m.created_at.slice(11, 16)) : ''}</div>
                    </div>
                `).join('')
                        : '<div class="msg-empty"><i class="fas fa-comments"></i><p>暂无消息，发送第一条吧</p></div>')}
            </div>
            <div class="conversation-input">
                <input type="text" id="conversation-msg-input" placeholder="输入消息..." maxlength="500" autocomplete="off" name="conversation-message">
                <button class="btn btn-primary conversation-send" id="conversation-send-btn" aria-label="发送消息">
                    <i class="fas fa-paper-plane" aria-hidden="true"></i>
                </button>
            </div>
        </div>
    `, 'fa-envelope');

    // 会话弹窗专用布局（固定高度 / 内部滚动，避免与 .detail-modal 的双滚动条打架）
    document.querySelector('.detail-modal .modal-content')?.classList.add('conv-modal');

    // 滚动到底部
    const msgContainer = document.getElementById('conversation-messages');
    if (msgContainer) msgContainer.scrollTop = msgContainer.scrollHeight;

    // 会话内实时刷新：对方发来的新消息自动出现，无需刷新页面
    startConvPolling(userId);

    // 发送按钮
    const sendBtn = document.getElementById('conversation-send-btn');
    const input = document.getElementById('conversation-msg-input');

    async function doSend() {
        const content = input?.value.trim();
        if (!content) return;
        try {
            const res = await apiCall('/api/messages/send', 'POST', {
                sender_id: myId, receiver_id: userId, content
            });
            // 添加气泡（打 data-mid，轮询时据此去重，避免重复）
            const bubble = document.createElement('div');
            bubble.className = 'msg-bubble mine';
            if (res && res.id !== null && res.id !== undefined) bubble.dataset.mid = 'i' + res.id;
            bubble.innerHTML = `<div class="msg-bubble-content">${escapeHtml(content)}</div><div class="msg-bubble-time">${escapeHtml(new Date().toTimeString().slice(0,5))}</div>`;
            // 移除空状态提示
            const empty = msgContainer.querySelector('.msg-empty');
            if (empty) empty.remove();
            msgContainer.appendChild(bubble);
            msgContainer.scrollTop = msgContainer.scrollHeight;
            input.value = '';
            updateBadgeCount();
        } catch(e) {
            showNotification('发送失败', 'error');
        }
    }

    sendBtn?.addEventListener('click', doSend);
    input?.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); doSend(); }
    });
    input?.focus();
}

async function markAllNotificationsRead() {
    const userId = currentUserId();
    if (!userId) return;
    try {
        await apiCall('/api/notifications/read', 'POST', { user_id: userId });
        loadNotifications();
        updateBadgeCount();
        showNotification('已全部标记为已读', 'success');
    } catch(e) {
        showNotification('操作失败', 'error');
    }
}

async function clearReadNotifications() {
    const userId = currentUserId();
    if (!userId) return;
    try {
        await apiCall(`/api/notifications/clear?user_id=${userId}`, 'DELETE');
        loadNotifications();
        showNotification('已清除已读通知', 'success');
    } catch(e) {
        showNotification('操作失败', 'error');
    }
}

async function showComposeModal() {
    // 关闭下拉面板
    document.getElementById('msg-dropdown')?.classList.remove('show');

    // ⚠️ 名册行 ≠ 平台账号（2026-10-07 修正）：
    //   此前收件人下拉的 value 用的是**名册号**（STU001），而 messages 表全站按
    //   username 收发 → 消息写进库里后学员永远看不到（消息中心只会按自己的账号查）。
    //   现在只列**已关联平台账号**的学员，value 用 user_id（=username）。
    //   学员/企业等非教师角色没有「可主动发起对话的联系人」数据源，如实说明，
    //   不再去调教师接口（那会拿到 403，页面显示成「收件人加载失败」）。
    const role = (AppState.user && AppState.user.role) || '';
    if (role !== 'teacher') {
        showDetailModal('写消息', `
            <div class="teacher-form">
                <div class="teacher-form-hint" style="font-size:0.88rem">
                    平台暂不支持该角色主动发起新对话。对方（老师 / 企业）发来消息后，
                    可在消息中心对应条目上点「回复」继续沟通。
                </div>
            </div>
        `, 'fa-pen');
        return;
    }

    let students = [];
    let recvFailed = false;
    try {
        const data = await apiCall('/api/teacher/students');
        if (data.success) students = data.students || [];
        else recvFailed = true;
    } catch(e) { recvFailed = true; console.warn('[消息中心] 收件人列表加载失败', e); }

    const reachable = students.filter(s => s.user_id);
    const unlinked = students.length - reachable.length;

    showDetailModal('写消息', `
        <div class="teacher-form">
            <div class="form-group">
                <label>收件人</label>
                <select id="compose-receiver">
                    ${recvFailed
                        ? '<option value="">收件人加载失败，请关闭后重试</option>'
                        : '<option value="">选择收件人</option>' + reachable.map(s => `<option value="${escapeHtml(s.user_id)}">${escapeHtml(s.name)}（${escapeHtml(s.direction || '未分方向')}）</option>`).join('')}
                </select>
                ${(!recvFailed && !reachable.length)
                    ? '<div class="teacher-form-hint">还没有可发送的学员——学员需要先在「学员管理」里关联平台账号，才能收到站内消息。</div>'
                    : (unlinked > 0 ? `<div class="teacher-form-hint">另有 ${unlinked} 名学员尚未关联平台账号，无法接收消息（可在「学员管理」里关联）。</div>` : '')}
            </div>
            <div class="form-group">
                <label>消息内容</label>
                <textarea id="compose-content" rows="4" placeholder="输入消息内容..." maxlength="500"></textarea>
            </div>
            <button class="btn btn-primary teacher-form-submit" id="compose-send-btn">
                <i class="fas fa-paper-plane"></i> 发送
            </button>
        </div>
    `, 'fa-pen');

    document.getElementById('compose-send-btn')?.addEventListener('click', async () => {
        const receiverId = document.getElementById('compose-receiver')?.value;
        const content = document.getElementById('compose-content')?.value.trim();
        const senderId = currentUserId();
        if (!receiverId) { showNotification('请选择收件人', 'error'); return; }
        if (!content) { showNotification('请输入消息内容', 'error'); return; }
        try {
            const data = await apiCall('/api/messages/send', 'POST', {
                sender_id: senderId, receiver_id: receiverId, content
            });
            showNotification(data.message, data.success ? 'success' : 'error');
            if (data.success) {
                document.querySelector('.modal-overlay.detail-modal')?.remove();
                updateBadgeCount();
            }
        } catch(e) {
            showNotification('发送失败', 'error');
        }
    });
}

function showDetailModal(title, html, icon) {
    // 移除已有的
    document.querySelector('.modal-overlay.detail-modal')?.remove();

    const modal = document.createElement('div');
    modal.className = 'modal-overlay detail-modal';
    modal.style.display = 'flex';
    modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-modal', 'true');
    modal.setAttribute('aria-labelledby', 'detail-modal-title');
    // ⚠️ title 一律 escapeHtml（可能含用户可控文本，如学员姓名 / 政策标题）；
    //    图标必须走独立的 icon 参数（FontAwesome 类名，如 'fa-envelope'）——
    //    写进 title 里会被转义成字面 `<i ...>` 文本（历史 bug，已在调用处一并修正）。
    const iconHtml = icon ? `<i class="fas ${icon} modal-title-icon" aria-hidden="true"></i>` : '';
    modal.innerHTML = `
        <div class="modal-content">
            <div class="modal-header">
                <h3 id="detail-modal-title">${iconHtml}${escapeHtml(title)}</h3>
                <button class="modal-close detail-close" aria-label="关闭"><i class="fas fa-times"></i></button>
            </div>
            <div class="modal-body">${html}</div>
        </div>
    `;
    document.body.appendChild(modal);

    trapFocus(modal);
    modal.querySelector('.detail-close').addEventListener('click', () => modal.remove());
    modal.addEventListener('click', e => { if (e.target === modal) modal.remove(); });
}

// ==================== 连接检查 ====================

async function checkConnection() {
    const dot = document.querySelector('#connection-status .dot');
    try {
        const data = await apiCall('/api/health');
        if (data.success) {
            if (dot) dot.classList.add('connected');
        }
    } catch(e) {
        if (dot) dot.classList.remove('connected');
    }
}

// ==================== 通知 ====================

function showNotification(message, type = 'info', opts) {
    const notification = document.getElementById('notification');
    if (!notification) return;
    const msgSpan = notification.querySelector('.notification-message');
    const icon = notification.querySelector('i');

    msgSpan.textContent = message;
    icon.className = 'fas';
    // 移除旧的类型class
    notification.classList.remove('success', 'error', 'warning', 'info');
    notification.classList.add(type);
    switch(type) {
        case 'success': icon.classList.add('fa-check-circle'); break;
        case 'error': icon.classList.add('fa-exclamation-circle'); break;
        case 'warning': icon.classList.add('fa-exclamation-triangle'); break;
        default: icon.classList.add('fa-info-circle');
    }
    // 可选内联操作按钮（如未登录提示的「去登录」）
    const actBtn = document.getElementById('notification-action');
    if (actBtn) {
        if (opts && opts.actionLabel && typeof opts.action === 'function') {
            actBtn.textContent = opts.actionLabel;
            actBtn.classList.remove('is-hidden');
            actBtn.onclick = function (ev) {
                ev.stopPropagation();
                try { opts.action(); } finally { notification.classList.remove('show'); }
            };
        } else {
            actBtn.classList.add('is-hidden');
            actBtn.textContent = '';
            actBtn.onclick = null;
        }
    }
    notification.classList.add('show');
    // 定时器防抖：连续多条提示时，旧定时器不应把新提示提前收走
    clearTimeout(showNotification._hideTimer);
    const dur = (opts && opts.actionLabel) ? 6000 : 3000;
    showNotification._hideTimer = setTimeout(() => notification.classList.remove('show'), dur);
}

/* 统一的「复制到剪贴板」：带能力检测 + 失败提示。
   非 HTTPS（本项目默认 http://localhost）或写入被拒时，旧实现直接 .then() 无 catch
   → 点了没反应。此处统一走这里。 */
function copyText(text, okMsg) {
    if (!navigator.clipboard || !navigator.clipboard.writeText) {
        showNotification('当前浏览器不支持自动复制，请手动选择文本', 'warning');
        return Promise.resolve(false);
    }
    return navigator.clipboard.writeText(text).then(
        function () { if (okMsg) showNotification(okMsg, 'success'); return true; },
        function () { showNotification('复制失败，请手动选择文本', 'warning'); return false; }
    );
}

function showLoading(message = '加载中...') {
    const overlay = document.getElementById('loading-overlay');
    const msgEl = document.getElementById('loading-message');
    const progressText = document.getElementById('loading-progress-text');
    if (overlay) {
        overlay.classList.remove('is-hidden');
        if (msgEl) msgEl.textContent = message;
        if (progressText) progressText.textContent = message;
    }
}

function hideLoading() {
    const overlay = document.getElementById('loading-overlay');
    if (overlay) overlay.classList.add('is-hidden');
}

function toggleShortcutsHelp() {
    showNotification('帮助：使用顶部导航切换功能模块，点击卡片探索各项功能', 'info');
}

// ==================== 滚动动画 ====================

function setupScrollReveal() {
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('revealed');
            }
        });
    }, { threshold: 0.1 });

    // Only observe hero section elements — no scroll-reveal on content tabs
    document.querySelectorAll('.hero .scroll-reveal').forEach(el => {
        observer.observe(el);
    });
}

// ==================== 导航栏滚动效果 ====================

function setupNavbarScroll() {
    const navbar = document.querySelector('.navbar');
    if (!navbar) return;

    let ticking = false;
    window.addEventListener('scroll', () => {
        if (!ticking) {
            window.requestAnimationFrame(() => {
                if (window.scrollY > 50) {
                    navbar.classList.add('scrolled');
                } else {
                    navbar.classList.remove('scrolled');
                }
                ticking = false;
            });
            ticking = true;
        }
    });
}

// ==================== Hero粒子动画 ====================

function setupHeroParticles() {
    if (prefersReducedMotion) return;
    const canvas = document.getElementById('hero-particles');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    let particles = [];
    let animationId;

    function resize() {
        canvas.width = canvas.parentElement.offsetWidth;
        canvas.height = canvas.parentElement.offsetHeight;
    }

    function createParticles() {
        particles = [];
        // Reduced density — Apple-style minimal particles
        const count = Math.floor((canvas.width * canvas.height) / 35000);
        for (let i = 0; i < count; i++) {
            particles.push({
                x: Math.random() * canvas.width,
                y: Math.random() * canvas.height,
                size: Math.random() * 1.5 + 0.5,
                speedX: (Math.random() - 0.5) * 0.2,
                speedY: (Math.random() - 0.5) * 0.2,
                opacity: Math.random() * 0.3 + 0.1
            });
        }
    }

    function animate() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        particles.forEach(p => {
            p.x += p.speedX;
            p.y += p.speedY;

            if (p.x < 0) p.x = canvas.width;
            if (p.x > canvas.width) p.x = 0;
            if (p.y < 0) p.y = canvas.height;
            if (p.y > canvas.height) p.y = 0;

            ctx.beginPath();
            ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(255, 255, 255, ${p.opacity})`;
            ctx.fill();
        });

        // 连线效果 — 更克制的连接
        for (let i = 0; i < particles.length; i++) {
            for (let j = i + 1; j < particles.length; j++) {
                const dx = particles[i].x - particles[j].x;
                const dy = particles[i].y - particles[j].y;
                const dist = Math.sqrt(dx * dx + dy * dy);
                if (dist < 80) {
                    ctx.beginPath();
                    ctx.moveTo(particles[i].x, particles[i].y);
                    ctx.lineTo(particles[j].x, particles[j].y);
                    ctx.strokeStyle = `rgba(255, 255, 255, ${0.05 * (1 - dist / 80)})`;
                    ctx.lineWidth = 0.5;
                    ctx.stroke();
                }
            }
        }

        animationId = requestAnimationFrame(animate);
    }

    resize();
    createParticles();
    animate();

    const debouncedResize = debounce(() => {
        resize();
        createParticles();
    }, 200);
    window.addEventListener('resize', debouncedResize);

    // 页面不可见时暂停动画
    document.addEventListener('visibilitychange', () => {
        if (document.hidden) {
            if (animationId) { cancelAnimationFrame(animationId); animationId = null; }
        } else {
            if (!animationId) animate();
        }
    });
}

// ==================== 数字滚动动画 ====================

function setupStatCounter() {
    const statNumbers = document.querySelectorAll('.stat-number[data-key]');
    if (statNumbers.length === 0) return;

    // P1-3：统计数字须接真实库计数（红线「不编造」），不再写死假数据。
    // 先取 /api/home/stats，按 data-key 映射；接口失败则按 0 渲染（不编造兜底值）。
    let stats = null;
    apiCall('/api/home/stats').then(function (res) {
        if (res && res.success && res.stats) stats = res.stats;
    }).catch(function () {
        stats = null;
    }).then(function () {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const el = entry.target;
                    const target = parseInt(el.getAttribute('data-target')) || 0;
                    if (prefersReducedMotion) {
                        el.textContent = target.toLocaleString();
                    } else {
                        animateNumber(el, target);
                    }
                    observer.unobserve(el);
                }
            });
        }, { threshold: 0.5 });

        statNumbers.forEach(el => {
            const key = el.getAttribute('data-key');
            const val = (stats && stats[key] != null) ? parseInt(stats[key], 10) : 0;
            el.setAttribute('data-target', String(val));
            el.textContent = '0';
            observer.observe(el);
        });
    });
}

function animateNumber(el, target) {
    const duration = 2000;
    const start = performance.now();
    const startVal = 0;

    function update(now) {
        const elapsed = now - start;
        const progress = Math.min(elapsed / duration, 1);
        // easeOutExpo
        const eased = progress === 1 ? 1 : 1 - Math.pow(2, -10 * progress);
        const current = Math.floor(startVal + (target - startVal) * eased);
        el.textContent = current.toLocaleString();

        if (progress < 1) {
            requestAnimationFrame(update);
        } else {
            // 小清理（2026-10-05）：原在末尾拼 '+' 后缀（如「86+」），无业务含义且易误读
            // 为「86 分以上」，已移除。
            el.textContent = target.toLocaleString();
        }
    }

    requestAnimationFrame(update);
}

// ==================== 本土资源 · 本地成功案例 ====================
// 内容唯一事实源 = 后端 cases_data.py（经 /api/resources/cases 下发）。
// 首页卡片与 case-detail.html 详情页共用同一份数据，避免两处写死、各改各的。
let _casesLoaded = false;

async function loadSuccessCases(force) {
    const grid = document.getElementById('cases-grid');
    if (!grid) return;
    if (_casesLoaded && !force) return;

    grid.innerHTML = '<div class="cases-placeholder"><i class="fas fa-spinner fa-spin"></i> 正在加载案例…</div>';

    try {
        const res = await fetch('/api/resources/cases');
        if (!res.ok) throw new Error('HTTP ' + res.status);
        const data = await res.json();
        if (!data.success || !Array.isArray(data.cases)) {
            throw new Error(data.message || '返回数据格式异常');
        }
        if (data.cases.length === 0) {
            // 案例需超级管理员审核后才可见。全部待审 ≠ 接口出错，要分开呈现，
            // 否则会把"审核中"显示成"加载失败"，让人误判系统坏了。
            const stat = data.case_review || {};
            if ((stat.pending || 0) > 0) {
                grid.innerHTML = `
                    <div class="cases-pending">
                        <i class="fas fa-user-shield"></i>
                        <p>案例内容正在审核中（${stat.pending} 条待审）</p>
                        <span>本地成功案例需经超级管理员审核通过后展示</span>
                    </div>`;
                _casesLoaded = true;
                return;
            }
            // 一条案例都没有 —— 这才是真异常
            throw new Error('暂无案例数据');
        }
        renderSuccessCases(data.cases);
        _casesLoaded = true;
    } catch (e) {
        console.error('加载成功案例失败:', e);
        grid.innerHTML = `
            <div class="cases-error">
                <i class="fas fa-exclamation-circle"></i>
                <p>案例加载失败：${escapeHtml(e.message || '未知错误')}</p>
                <button class="btn btn-outline btn-sm" onclick="loadSuccessCases(true)">
                    <i class="fas fa-redo"></i> 重试
                </button>
            </div>`;
    }
}

function renderSuccessCases(cases) {
    const grid = document.getElementById('cases-grid');
    if (!grid) return;
    grid.innerHTML = cases.map(c => {
        // 卡片上只放两条最关键的指标，其余在详情页展开
        const stats = Array.isArray(c.stats) ? c.stats.slice(0, 2) : [];
        const statsHtml = stats.map(s =>
            `<span><i class="fas ${s.icon || 'fa-chart-line'}"></i> ${escapeHtml(s.label)}：${escapeHtml(s.value)}</span>`
        ).join('');
        return `
        <div class="case-card">
            <div class="case-visual"><i class="fas fa-map-marker-alt"></i></div>
            <div class="case-body">
                <h4>${escapeHtml(c.title)}</h4>
                <p>${escapeHtml(c.description || '')}</p>
                <div class="case-stats">${statsHtml}</div>
                <a href="case-detail.html?id=${encodeURIComponent(c.id)}" class="btn btn-outline btn-sm" target="_blank">
                    查看详情 <i class="fas fa-external-link-alt"></i>
                </a>
            </div>
        </div>`;
    }).join('');
}

// ==================== 平滑滚动 ====================

function setupSmoothScroll() {
    document.querySelectorAll('a[href^="#"]').forEach(link => {
        link.addEventListener('click', function(e) {
            const targetId = this.getAttribute('href');
            if (targetId === '#') return;
            const target = document.querySelector(targetId);
            if (target) {
                e.preventDefault();
                target.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        });
    });
}

// ==================== 导出 ====================

window.switchTab = switchTab;
window.toggleShortcutsHelp = toggleShortcutsHelp;
// 案例/政策卡片错误态里的"重试"按钮走内联 onclick，需挂到 window
window.loadSuccessCases = loadSuccessCases;
window.loadPolicies = loadPolicies;

// ==================== 注册/登录 Tab 切换 ====================

function setupAuthTabs() {
    const tabLogin = document.getElementById('auth-tab-login');
    const tabRegister = document.getElementById('auth-tab-register');
    const loginForm = document.getElementById('auth-login-form');
    const regForm = document.getElementById('auth-register-form');
    if (!tabLogin || !tabRegister) return;

    tabLogin.addEventListener('click', () => {
        tabLogin.classList.add('active');
        tabRegister.classList.remove('active');
        loginForm.classList.remove('is-hidden');
        regForm.classList.add('is-hidden');
    });

    tabRegister.addEventListener('click', () => {
        tabRegister.classList.add('active');
        tabLogin.classList.remove('active');
        loginForm.classList.remove('is-hidden');
        regForm.classList.add('is-hidden');
        // 实际切换
        loginForm.classList.add('is-hidden');
        regForm.classList.remove('is-hidden');
    });

    // 注册角色选择 - 显示/隐藏公司名
    const regRole = document.getElementById('reg-role');
    const companyGroup = document.getElementById('reg-company-group');
    if (regRole && companyGroup) {
        regRole.addEventListener('change', () => {
            companyGroup.classList.toggle('is-hidden', regRole.value !== 'enterprise');
        });
    }
}

// 重置认证Tab到登录状态
function resetAuthTabs() {
    const tabLogin = document.getElementById('auth-tab-login');
    const tabRegister = document.getElementById('auth-tab-register');
    const loginForm = document.getElementById('auth-login-form');
    const regForm = document.getElementById('auth-register-form');
    if (tabLogin && tabRegister) {
        tabLogin.classList.add('active');
        tabRegister.classList.remove('active');
    }
    if (loginForm && regForm) {
        loginForm.classList.remove('is-hidden');
        regForm.classList.add('is-hidden');
    }
}

// ==================== 注册处理 ====================

function setupRegister() {
    const btn = document.getElementById('register-submit');
    if (!btn) return;
    btn.addEventListener('click', async () => {
        const username = document.getElementById('reg-username').value.trim();
        const password = document.getElementById('reg-password').value.trim();
        const name = document.getElementById('reg-name').value.trim();
        const role = document.getElementById('reg-role').value;
        const phone = document.getElementById('reg-phone').value.trim();
        const region = document.getElementById('reg-region').value.trim();
        const company = document.getElementById('reg-company')?.value.trim() || '';

        if (!username || !password || !name) {
            showNotification('请填写用户名、密码和姓名', 'error');
            return;
        }
        if (password.length < 6) {
            showNotification('密码至少6位', 'error');
            return;
        }

        try {
            const resp = await apiCall('/api/auth/register', 'POST', {
                username, password, name, role, phone, company_name: company, region
            });
            if (resp.success) {
                AppState.sessionId = resp.session_id;
                AppState.user = normalizeUser(resp.user);
                saveSession();
                document.getElementById('login-modal').classList.add('is-hidden');
                resetAuthTabs();
                // 角色分流
                var _r = resp.user.role;
                if (_r === 'super_admin') { location.href = 'admin.html'; return; }
                if (_r === 'government') { location.href = 'government.html'; return; }
                if (_r === 'enterprise') { location.href = 'enterprise.html'; return; }
                if (_r === 'teacher') { location.href = 'teacher.html'; return; }
                onLoginSuccess();
                showNotification(resp.message || '注册成功', 'success');
            } else {
                showNotification(resp.message || '注册失败', 'error');
            }
        } catch (e) {
            showNotification('注册失败：' + e.message, 'error');
        }
    });
}

// ==================== 角色权限配置 ====================

const ROLE_NAV = {
    student:     ['agriculture', 'ecommerce', 'crafts', 'resources', 'employment'],
    teacher:     ['agriculture', 'ecommerce', 'crafts', 'resources', 'employment', 'teacher'],
    super_admin: ['admin'],
    government:  ['government'],
    enterprise:  ['enterprise']
};

const ROLE_DEFAULT = {
    student: 'agriculture', teacher: 'teacher', super_admin: 'admin',
    government: 'government', enterprise: 'enterprise'
};

// 这三个角色的工作台是独立门户页，主站没有对应面板（ROLE_DEFAULT 指向的
// admin/government/enterprise tab 在 index.html 里并不存在）→ 登录主站会整页空白。
// 2026-10-09：改为在主站给一张引导卡，把他们送到各自的门户页。
const ROLE_PORTAL = {
    super_admin: {
        title: '系统管理后台',
        desc: '账号管理、内容审核、系统公告与内容监管都在管理后台进行，主站不提供管理面板。',
        btn: '进入管理后台', page: 'admin.html'
    },
    government: {
        title: '政府工作端',
        desc: '政策发布与本地案例管理在政府工作端进行，主站不提供政府面板。',
        btn: '进入政府工作端', page: 'government.html'
    },
    enterprise: {
        title: '企业服务端',
        desc: '岗位发布、招聘管理与投递处理在企业服务端进行，主站不提供企业面板。',
        btn: '进入企业服务端', page: 'enterprise.html'
    }
};

function getAllowedTabs(role) {
    return ROLE_NAV[role] || ROLE_NAV['student'];
}

function isTabAllowed(tabName, role) {
    return getAllowedTabs(role).includes(tabName);
}

// ==================== 角色UI切换 ====================

// 该角色在主站是否有真实面板：看 ROLE_DEFAULT 指向的 #xxx-tab 元素存不存在。
// 用「元素是否存在」判断而不是硬编码角色名，以后新增角色会自动适配。
function hasMainSitePanel(role) {
    const tab = ROLE_DEFAULT[role];
    return !!(tab && document.getElementById(tab + '-tab'));
}

// 无主站面板的角色 → 显示引导卡，把他送到对应门户页（不再是一片空白）。
function applyRolePortalCard(role) {
    const card = document.getElementById('role-portal-card');
    if (!card) return;
    const entry = ROLE_PORTAL[role];
    if (!entry || hasMainSitePanel(role)) {
        card.classList.add('is-hidden');
        return;
    }
    document.getElementById('role-portal-title').textContent = entry.title;
    document.getElementById('role-portal-desc').textContent = entry.desc;
    const link = document.getElementById('role-portal-link');
    link.textContent = entry.btn;
    link.setAttribute('href', entry.page);
    card.classList.remove('is-hidden');
}

function applyRoleVisibility(role) {
    // 0) 工作台引导卡：无主站面板的角色显示，其余隐藏
    applyRolePortalCard(role);

    // 1) 导航栏：只显示该角色允许的 tab，隐藏其余
    document.querySelectorAll('#nav-menu .nav-item').forEach(btn => {
        const tab = btn.getAttribute('data-tab');
        const allowed = isTabAllowed(tab, role);
        btn.classList.toggle('is-hidden', !allowed);
        if (!allowed) {
            btn.classList.remove('active');
            btn.setAttribute('aria-selected', 'false');
        }
    });

    // 2) 页面区域：隐藏不属于该角色的 Hero
    const hero = document.getElementById('hero');
    const isPublicRole = (role === 'student' || role === 'teacher');
    if (hero) hero.classList.toggle('is-hidden', !isPublicRole);

    // 3) 消息中心：所有已登录角色可见（修正理由见 updateUserUI 内注释）
    const quickMenu = document.getElementById('teacher-quick-menu');
    if (quickMenu) quickMenu.classList.toggle('is-hidden', !role);
}

function onLoginSuccess() {
    const user = AppState.user;
    if (!user) return;
    updateUserUI(user);

    const role = user.role;

    // 角色导航过滤：隐藏该角色无权访问的顶级 tab，并按角色显隐 Hero / 教师快速菜单
    applyRoleVisibility(role);

    // 登录后：补发当月已到期的农事提醒 + 同步订阅按钮选中态（均幂等，失败静默）
    checkFarmingReminders();
    syncFarmingSubscriptionButton();

    // 消息红点：setupQuickMessage() 在 initializeApp 的 setupFns 里排在 restoreSession
    // **之前**，执行时 AppState.user 仍为 null → currentUserId() 为空 → 直接 return，
    // 之后再无人调用 → 刷新页面后红点永远停在初始的「0/隐藏」。
    // 这里在会话就绪后补一次（登录的 handleLogin 路径同样经过 onLoginSuccess）。
    updateBadgeCount();
    // 并开启未读红点轮询（对方新消息 → 本端红点也能自动出现，见 updateBadgeCount 上方注释）
    startBadgePolling();

    // 元素级角色可见性（散落在页面内的角色专属区块）
    document.querySelectorAll('.teacher-only').forEach(el => el.classList.toggle('is-hidden', role !== 'teacher'));
    document.querySelectorAll('.admin-only').forEach(el => el.classList.toggle('is-hidden', role !== 'super_admin'));
    document.querySelectorAll('.gov-only').forEach(el => el.classList.toggle('is-hidden', role !== 'government'));
    document.querySelectorAll('.enterprise-only').forEach(el => el.classList.toggle('is-hidden', role !== 'enterprise'));

    // 强制跳转到角色默认首页
    const defaultTab = ROLE_DEFAULT[role] || 'agriculture';
    switchTab(defaultTab);

    // 触发首次数据加载
    if (role === 'government') loadGovDashboard();
    else if (role === 'enterprise') loadEnterpriseJobs();
    else if (role === 'teacher') loadTeacherDashboard();
}

// ==================== 公开视图恢复 ====================

function resetToPublicView() {
    // 显示所有公开导航项 (student tabs)
    document.querySelectorAll("#nav-menu .nav-item").forEach(function(btn) {
        var tab = btn.getAttribute("data-tab");
        var allowed = ROLE_NAV["student"].indexOf(tab) >= 0;
        btn.classList.toggle("is-hidden", !allowed);
        btn.classList.remove("active");
        btn.setAttribute("aria-selected", "false");
    });
    // 恢复 Hero / Features
    var hero = document.getElementById("hero");
    var features = document.getElementById("features");
    if (hero) hero.classList.remove("is-hidden");
    if (features) features.classList.remove("is-hidden");
    // 隐藏教师快速菜单
    var quickMenu = document.getElementById("teacher-quick-menu");
    if (quickMenu) quickMenu.classList.add("is-hidden");
    // 退出登录：停止未读红点轮询 / 会话内实时刷新
    stopBadgePolling();
    stopConvPolling();
    // 更新UI到未登录状态
    var loginSection = document.getElementById("login-section");
    var userInfo = document.getElementById("user-info");
    if (loginSection) loginSection.classList.remove("is-hidden");
    if (userInfo) userInfo.classList.add("is-hidden");
    // 隐藏工作台引导卡 —— 未登录态不该留着「进入管理后台」这类入口
    var rolePortalCard = document.getElementById("role-portal-card");
    if (rolePortalCard) rolePortalCard.classList.add("is-hidden");
    // 回到农业技能首页
    switchTab("agriculture");
}

function saveSession() {
    localStorage.setItem(STORAGE_KEYS.SESSION, JSON.stringify({
        sessionId: AppState.sessionId,
        user: AppState.user
    }));
}

// ==================== 政府人员功能 ====================

function loadGovDashboard() {
    apiCall('/api/government/dashboard', 'GET').then(resp => {
        const content = document.getElementById('gov-dashboard-content');
        if (!content || !resp.success) return;
        const d = resp.overview;
        const dirs = (resp.directions || []).map(d => `${d.direction}: ${d.count}人 (均${d.avg_progress}%)`).join('<br>');
        content.innerHTML = `
            <div class="dashboard-cards">
                <div class="dash-card"><h4>👥 用户</h4>
                    <p>总计 ${d.users.total} | 学员 ${d.users.students} | 教师 ${d.users.teachers} | 企业 ${d.users.enterprises}</p></div>
                <div class="dash-card"><h4>📚 培训</h4>
                    <p>学员 ${d.training.total_students} | 平均进度 ${d.training.avg_progress}% | 完成率 ${d.training.completion_rate}%</p></div>
                <div class="dash-card"><h4>💼 就业</h4>
                    <p>岗位 ${d.employment.total_jobs} | 申请 ${d.employment.total_applications} | 匹配率 ${d.employment.match_rate}%</p></div>
                <div class="dash-card"><h4>📄 内容</h4>
                    <p>课程 ${d.content.courses} | 政策 ${d.content.policies}</p></div>
                <div class="dash-card"><h4>🎖 证书</h4>
                    <p>总数 ${d.certificates.total} | 已获 ${d.certificates.earned} | 获证率 ${d.certificates.earn_rate}%</p></div>
                <div class="dash-card"><h4>💬 社区</h4>
                    <p>讨论 ${d.community.discussions} | 评论 ${d.community.comments}</p></div>
            </div>
            <div class="dashboard-section"><h4>各地区分布</h4><p>${(resp.regions || []).map(r => `${r.region}: ${r.count}人`).join(' | ') || '暂无数据'}</p></div>
            <div class="dashboard-section"><h4>培训方向分布</h4><p>${dirs || '暂无数据'}</p></div>`;
    });
}

function loadGovPolicies() {
    apiCall('/api/government/policies', 'GET').then(resp => {
        const list = document.getElementById('gov-policies-list');
        if (!list) return;
        if (!resp.policies || resp.policies.length === 0) {
            list.innerHTML = '<p>暂无政策</p>';
            return;
        }
        list.innerHTML = resp.policies.map(p => `
            <div class="policy-card">
                <h4>${p.title} <small>${p.category}</small></h4>
                <p>${p.content.slice(0,200)}...</p>
                <div class="table-actions">
                    <button class="btn btn-xs" onclick="govTogglePolicy(${p.id},${p.is_published})">${p.is_published ? '下架' : '上架'}</button>
                    <button class="btn btn-xs btn-danger" onclick="govDeletePolicy(${p.id})">删除</button>
                </div>
            </div>`).join('');
    });
}

function govTogglePolicy(id, published) {
    apiCall(`/api/government/policies/${id}`, 'PUT', { is_published: published ? 0 : 1 }).then(resp => {
        if (resp.success) loadGovPolicies();
    });
}

function govDeletePolicy(id) {
    if (!confirm('确定删除此政策？')) return;
    apiCall(`/api/government/policies/${id}`, 'DELETE').then(resp => {
        if (resp.success) loadGovPolicies();
    });
}

function setupGovPolicyPublish() {
    const btn = document.getElementById('gov-publish-policy');
    if (!btn) return;
    btn.addEventListener('click', () => {
        const title = document.getElementById('gov-policy-title').value.trim();
        const content = document.getElementById('gov-policy-content').value.trim();
        const category = document.getElementById('gov-policy-category').value;
        if (!title || !content) { showNotification('标题和内容不能为空', 'error'); return; }
        apiCall('/api/government/policies', 'POST', { title, content, category }).then(resp => {
            showNotification(resp.message, resp.success ? 'success' : 'error');
            if (resp.success) {
                document.getElementById('gov-policy-title').value = '';
                document.getElementById('gov-policy-content').value = '';
                loadGovPolicies();
            }
        });
    });
}

// ==================== 企业功能 ====================

function loadEnterpriseJobs() {
    apiCall('/api/enterprise/jobs', 'GET').then(resp => {
        const list = document.getElementById('ent-jobs-list');
        if (!list) return;
        if (!resp.jobs || resp.jobs.length === 0) {
            list.innerHTML = '<p>暂无职位</p>';
            return;
        }
        list.innerHTML = resp.jobs.map(j => `
            <div class="job-card">
                <h4>${j.title}</h4>
                <p>${j.company} | ${j.salary} | ${j.location}</p>
                <span class="status-badge">${j.review_status || 'approved'}</span>
                <button class="btn btn-xs btn-danger" onclick="entDeleteJob(${j.id})">删除</button>
            </div>`).join('');
    });
}

function entDeleteJob(id) {
    if (!confirm('确定删除此职位？')) return;
    apiCall(`/api/enterprise/jobs/${id}`, 'DELETE').then(resp => {
        if (resp.success) loadEnterpriseJobs();
    });
}

function setupEntAddJob() {
    const btn = document.getElementById('ent-add-job-btn');
    if (!btn) return;
    btn.addEventListener('click', () => {
        const title = prompt('职位标题：');
        if (!title) return;
        const salary = prompt('薪资（如：5000-8000元/月）：', '');
        const location = prompt('工作地点：', '');
        const category = prompt('职位类别：', '');
        const description = prompt('职位描述：', '');
        apiCall('/api/enterprise/jobs', 'POST', { title, salary, location, category, description }).then(resp => {
            showNotification(resp.message, resp.success ? 'success' : 'error');
            if (resp.success) loadEnterpriseJobs();
        });
    });
}

/* 求购（供应链）相关函数已于 2026-10-06 整体下线：
   loadEnterpriseProcurements / entDeleteProc / setupEntAddProc
   原本引用 #ent-procs-list、#ent-add-proc-btn，而这两个节点在现版本 HTML 里
   早已不存在（属历史遗留死代码）。用户拍板「供应链求购不做」，此处一并清除。 */

function loadEnterpriseApplications() {
    apiCall('/api/enterprise/applications', 'GET').then(resp => {
        const list = document.getElementById('ent-apps-list');
        if (!list) return;
        if (!resp.applications || resp.applications.length === 0) {
            list.innerHTML = '<p>暂无简历投递</p>';
            return;
        }
        list.innerHTML = `<table class="data-table"><thead><tr><th>申请人</th><th>职位</th><th>电话</th><th>状态</th><th>时间</th><th>操作</th></tr></thead><tbody>
            ${resp.applications.map(a => `<tr>
                <td>${a.applicant_name || a.user_id}</td><td>${a.job_title}</td><td>${a.applicant_phone || '-'}</td>
                <td><span class="status-badge">${a.status}</span></td><td>${(a.applied_at || '').slice(0,10)}</td>
                <td class="table-actions">
                    <button class="btn btn-xs btn-success" onclick="entUpdateApp(${a.id},'interview')">面试</button>
                    <button class="btn btn-xs" onclick="entUpdateApp(${a.id},'approved')">通过</button>
                    <button class="btn btn-xs btn-danger" onclick="entUpdateApp(${a.id},'rejected')">拒绝</button>
                </td></tr>`).join('')}
            </tbody></table>`;
    });
}

function entUpdateApp(appId, status) {
    apiCall(`/api/enterprise/applications/${appId}`, 'PUT', { status }).then(resp => {
        showNotification(resp.message, resp.success ? 'success' : 'error');
        if (resp.success) loadEnterpriseApplications();
    });
}

// ==================== 讨论社区 ====================

function loadDiscussions() {
    const categoryMap = { 'disc-general': 'general', 'disc-agriculture': 'agriculture', 'disc-ecommerce': 'ecommerce', 'disc-crafts': 'crafts' };
    const activeTab = document.querySelector('#discussions-tab .sub-tab-btn.active');
    const cat = activeTab ? (categoryMap[activeTab.dataset.subtab] || 'general') : 'general';
    apiCall(`/api/discussions?category=${cat}`, 'GET').then(resp => {
        const list = document.getElementById('discussions-list');
        if (!list) return;
        if (!resp.discussions || resp.discussions.length === 0) {
            list.innerHTML = '<p>暂无讨论帖，快来发第一个帖子吧！</p>';
            return;
        }
        list.innerHTML = resp.discussions.map(d => `
            <div class="discussion-card">
                <h4><a href="#" onclick="viewDiscussion(${d.id});return false">${d.title}</a> ${d.is_pinned ? '📌' : ''}</h4>
                <p>${d.content.slice(0,150)}...</p>
                <small>${d.user_name || d.user_id} | ${d.created_at?.slice(0,16) || ''} | 👁 ${d.view_count} | 💬 ${d.comment_count}</small>
            </div>`).join('');
    });
}

function viewDiscussion(id) {
    apiCall(`/api/discussions/${id}`, 'GET').then(resp => {
        if (!resp.success) return showNotification(resp.message, 'error');
        const d = resp.discussion;
        const comments = resp.comments || [];
        let html = `<div class="modal-content" style="max-width:700px">
            <div class="modal-header"><h3>${d.title}</h3><button class="modal-close" onclick="this.closest('.modal-overlay').remove()"><i class="fas fa-times"></i></button></div>
            <div class="modal-body">
                <p>${d.content}</p><small>${d.user_name} | ${d.created_at?.slice(0,16) || ''} | 👁 ${d.view_count}</small>
                <hr><h4>评论 (${comments.length})</h4>
                ${comments.map(c => `<div class="comment-item"><strong>${c.user_name || c.user_id}</strong>: ${c.content} <small>${c.created_at?.slice(0,16) || ''}</small></div>`).join('')}
                ${AppState.user ? `<div class="form-group"><textarea id="disc-comment-content" placeholder="写评论..." rows="2" class="full-width"></textarea></div>
                <button class="btn btn-primary btn-sm" onclick="postDiscussionComment(${id})">发表评论</button>` : '<p>请登录后评论</p>'}
            </div></div>`;
        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay';
        overlay.innerHTML = html;
        document.body.appendChild(overlay);
        overlay.addEventListener('click', e => { if (e.target === overlay) overlay.remove(); });
    });
}

function postDiscussionComment(discId) {
    const content = document.getElementById('disc-comment-content')?.value.trim();
    if (!content) { showNotification('请输入评论内容', 'error'); return; }
    apiCall('/api/comments', 'POST', { target_type: 'discussion', target_id: discId, content }).then(resp => {
        showNotification(resp.message, resp.success ? 'success' : 'error');
        if (resp.success) {
            document.querySelectorAll('.modal-overlay').forEach(el => el.remove());
            viewDiscussion(discId);
        }
    });
}

function setupNewDiscussion() {
    const btn = document.getElementById('new-discussion-btn');
    if (!btn) return;
    btn.addEventListener('click', () => {
        if (!AppState.user) { showNotification('请先登录', 'error', { actionLabel: '去登录', action: openLoginModal }); return; }
        const title = prompt('帖子标题：');
        if (!title) return;
        const content = prompt('帖子内容：');
        if (!content) return;
        const category = document.querySelector('#discussions-tab .sub-tab-btn.active')?.dataset.subtab?.replace('disc-', '') || 'general';
        apiCall('/api/discussions', 'POST', { title, content, category }).then(resp => {
            showNotification(resp.message, resp.success ? 'success' : 'error');
            if (resp.success) loadDiscussions();
        });
    });
}

// ==================== 子Tab切换（管理员/政府/企业面板） ====================

function setupAdminSubTabs() {
    document.querySelectorAll('.admin-sub-tabs').forEach(tabBar => {
        tabBar.addEventListener('click', e => {
            if (!e.target.classList.contains('sub-tab-btn')) return;
            const subtab = e.target.dataset.subtab;
            const panel = e.target.closest('.tab-content');
            // 更新按钮状态
            tabBar.querySelectorAll('.sub-tab-btn').forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');
            // 显示对应面板
            panel.querySelectorAll('.sub-tab-panel').forEach(p => p.classList.add('is-hidden'));
            const targetPanel = document.getElementById(`${subtab}-panel`);
            if (targetPanel) targetPanel.classList.remove('is-hidden');
            // 加载数据
            if (subtab === 'gov-dashboard') loadGovDashboard();
            else if (subtab === 'gov-policies') loadGovPolicies();
            else if (subtab === 'ent-jobs') loadEnterpriseJobs();
            else if (subtab === 'ent-applications') loadEnterpriseApplications();
            else if (subtab.startsWith('disc-')) loadDiscussions();
        });
    });
}

// ==================== 初始化所有新功能 ====================

function setupNewFeatures() {
    setupAuthTabs();
    setupRegister();
    setupAdminSubTabs();
    setupGovPolicyPublish();
    setupEntAddJob();
    setupNewDiscussion();
}

// 追加到 DOMContentLoaded
document.addEventListener('DOMContentLoaded', function() {
    try { setupNewFeatures(); } catch(e) { console.error('setupNewFeatures error:', e); }
});
