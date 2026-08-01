// 粤乡智匠 — 功能模块（依赖 js/core.js）

// ==================== 初始化 ====================

document.addEventListener('DOMContentLoaded', function() {
    fixIOSViewport();
    initializeApp();
    registerServiceWorker();
});

function initializeApp() {
    showNotification('提示：点击了解项目功能', 'info');
    checkOnboarding();
    const setupFns = [
        setupNavigation, setupFeatureTabs, setupLoginModal,
        setupProductSelection, setupCraftSelection, setupDialectSelection,
        setupVoiceInput, setupAgricultureQA, setupCalendar,
        setupSimulationModules, setupEventListeners, setupUserDropdown,
        setupCaseButtons, setupEmploymentTab, setupPolicySection,
        setupTeacherPanel, setup3DControls, setupQuickMessage,
        restoreSession, checkConnection, setupScrollReveal,
        setupNavbarScroll, setupHeroParticles, setupStatCounter,
        setupSmoothScroll, setupThemeToggle, setupHamburger, setupPointsExchange
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

function restoreSession() {
    const saved = localStorage.getItem(STORAGE_KEYS.SESSION);
    if (!saved) return;
    try {
        const { sessionId, user } = JSON.parse(saved);
        AppState.sessionId = sessionId;
        AppState.user = user;
        apiCall('/api/auth/verify', 'POST', { session_id: sessionId })
            .then(data => {
                if (data.success) {
                    AppState.user = data.user;
                    updateUserUI();
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

function setupFeatureTabs() {
    document.querySelectorAll('.feature-tab').forEach(tab => {
        tab.addEventListener('click', function() {
            switchTab(this.getAttribute('data-tab'));
        });
    });
}

function switchTab(tabName) {
    // 更新导航栏active + ARIA
    document.querySelectorAll('.nav-item').forEach(item => {
        const isActive = item.getAttribute('data-tab') === tabName;
        item.classList.toggle('active', isActive);
        item.setAttribute('aria-selected', isActive);
    });
    // 更新feature tabs active + ARIA
    document.querySelectorAll('.feature-tab').forEach(tab => {
        const isActive = tab.getAttribute('data-tab') === tabName;
        tab.classList.toggle('active', isActive);
        tab.setAttribute('aria-selected', isActive);
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
            const featuresSection = document.getElementById('features');
            if (featuresSection) {
                featuresSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        }
        // 更新面包屑
        const tabNames = {
            agriculture: '农业技能', ecommerce: '电商运营', crafts: '手工传承',
            simulation: '虚拟实训', resources: '本土资源', employment: '就业对接',
            teacher: '教师管理'
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
        trapFocus(loginModal);
    });
    closeBtn?.addEventListener('click', () => loginModal.classList.add('is-hidden'));
    submitBtn?.addEventListener('click', handleLogin);
    demoBtn?.addEventListener('click', handleDemoLogin);
    logoutBtn?.addEventListener('click', handleLogout);

    // 演示账户点击填充
    document.querySelectorAll('.demo-account').forEach(el => {
        el.addEventListener('click', function() {
            document.getElementById('login-username').value = this.dataset.username;
            document.getElementById('login-password').value = this.dataset.password;
            document.getElementById('user-role-select').value = this.dataset.role;
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
            AppState.user = data.user;
            localStorage.setItem(STORAGE_KEYS.SESSION, JSON.stringify({
                sessionId: data.session_id,
                user: data.user
            }));
            document.getElementById('login-modal').classList.add('is-hidden');
            updateUserUI();
            showNotification(`欢迎回来，${data.user.name}！`, 'success');
            loadUserData();
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
    document.getElementById('user-role-select').value = 'student';
    handleLogin();
}

async function handleLogout() {
    if (AppState.sessionId) {
        try { await apiCall('/api/auth/logout', 'POST', { session_id: AppState.sessionId }); } catch(e) {}
    }
    AppState.sessionId = null;
    AppState.user = null;
    localStorage.removeItem('yuexiang_session');
    document.getElementById('login-section').classList.remove('is-hidden');
    document.getElementById('user-info').classList.add('is-hidden');
    document.getElementById('teacher-quick-menu').classList.add('is-hidden');
    document.querySelectorAll('.teacher-only').forEach(el => el.classList.add('is-hidden'));
    showNotification('已退出登录', 'info');
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
        document.getElementById('teacher-quick-menu').classList.remove('is-hidden');
    } else {
        document.querySelectorAll('.teacher-only').forEach(el => el.classList.add('is-hidden'));
        document.getElementById('teacher-quick-menu').classList.add('is-hidden');
    }
}

async function loadUserData() {
    if (!AppState.user) return;
    try {
        const ptsData = await apiCall(`/api/employment/points/${AppState.user.id}`);
        if (ptsData.success) {
            const el = document.getElementById('points-balance');
            if (el) el.textContent = ptsData.points.toLocaleString();
            const el2 = document.getElementById('emp-points-balance');
            if (el2) el2.textContent = ptsData.points.toLocaleString();
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

async function showSettingsModal() {
    const user = AppState.user || {};
    let profileData = null;
    try {
        const data = await apiCall('/api/user/profile');
        if (data.success) profileData = data.user;
    } catch(e) {}

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
                    <div class="wx-cell-icon"><i class="fas fa-book-open"></i></div>
                    <span class="wx-cell-label">我的动态</span>
                    <span class="wx-cell-value"></span>
                    <i class="fas fa-chevron-right wx-cell-arrow"></i>
                </div>
                <div class="wx-cell" id="wx-cell-my-assignments">
                    <div class="wx-cell-icon orange"><i class="fas fa-file-lines"></i></div>
                    <span class="wx-cell-label">我的作业</span>
                    <span class="wx-cell-value"></span>
                    <i class="fas fa-chevron-right wx-cell-arrow"></i>
                </div>
                <div class="wx-cell" id="wx-cell-my-attendance">
                    <div class="wx-cell-icon green"><i class="fas fa-clipboard-check"></i></div>
                    <span class="wx-cell-label">我的考勤</span>
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
                        <input type="checkbox" id="wx-notif-toggle" checked>
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

    // 我的动态
    document.getElementById('wx-cell-my-posts')?.addEventListener('click', () => {
        showSettingsSubPage('my-posts', {});
    });

    // 我的作业
    document.getElementById('wx-cell-my-assignments')?.addEventListener('click', () => {
        showSettingsSubPage('my-assignments', {});
    });

    // 我的考勤
    document.getElementById('wx-cell-my-attendance')?.addEventListener('click', () => {
        showSettingsSubPage('my-attendance', {});
    });

    // 深色模式开关
    document.getElementById('wx-dark-toggle')?.addEventListener('change', (e) => {
        const theme = e.target.checked ? 'dark' : 'light';
        document.documentElement.dataset.theme = theme;
        localStorage.setItem(STORAGE_KEYS.THEME, theme);
        updateThemeIcon();
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
                        <span class="wx-cell-label">头像</span>
                        <div class="wx-cell-avatar-preview"><i class="fas fa-user"></i></div>
                        <i class="fas fa-chevron-right wx-cell-arrow"></i>
                    </div>
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
                        <span class="wx-cell-value">通知 · 作业 · 签到 · 分析</span>
                    </div>
                    <div class="wx-cell">
                        <span class="wx-cell-label">技术支持</span>
                        <span class="wx-cell-value">AI + Flask + SQLite</span>
                    </div>
                </div>
            </div>
        `;

    } else if (page === 'my-posts') {
        // 我的动态 — 加载通知公告列表
        modalBody.innerHTML = `
            <div class="wx-sub-page">
                <div class="wx-sub-header">
                    <button class="wx-back-btn" onclick="showSettingsModal()"><i class="fas fa-chevron-left"></i> 返回</button>
                    <span class="wx-sub-title">我的动态</span>
                    <span></span>
                </div>
                <div id="wx-posts-list" class="wx-list-container">
                    <div class="wx-loading"><div class="spinner"></div> 加载中...</div>
                </div>
            </div>
        `;
        loadMyPosts();

    } else if (page === 'my-assignments') {
        // 我的作业
        modalBody.innerHTML = `
            <div class="wx-sub-page">
                <div class="wx-sub-header">
                    <button class="wx-back-btn" onclick="showSettingsModal()"><i class="fas fa-chevron-left"></i> 返回</button>
                    <span class="wx-sub-title">我的作业</span>
                    <span></span>
                </div>
                <div id="wx-assignments-list" class="wx-list-container">
                    <div class="wx-loading"><div class="spinner"></div> 加载中...</div>
                </div>
            </div>
        `;
        loadMyAssignments();

    } else if (page === 'my-attendance') {
        // 我的考勤
        modalBody.innerHTML = `
            <div class="wx-sub-page">
                <div class="wx-sub-header">
                    <button class="wx-back-btn" onclick="showSettingsModal()"><i class="fas fa-chevron-left"></i> 返回</button>
                    <span class="wx-sub-title">我的考勤</span>
                    <span></span>
                </div>
                <div id="wx-attendance-list" class="wx-list-container">
                    <div class="wx-loading"><div class="spinner"></div> 加载中...</div>
                </div>
            </div>
        `;
        loadMyAttendance();
    }
}

async function loadMyPosts() {
    const container = document.getElementById('wx-posts-list');
    if (!container) return;
    try {
        const data = await apiCall('/api/student/announcements');
        if (!data.success || !data.announcements.length) {
            container.innerHTML = '<div class="wx-empty"><i class="fas fa-bullhorn"></i><p>暂无动态</p></div>';
            return;
        }
        container.innerHTML = `<div class="wx-cell-group">${data.announcements.map(a => {
            const catColors = { '通知': 'blue', '公告': 'gray', '紧急': 'orange' };
            const catCls = catColors[a.category] || 'blue';
            return `
                <div class="wx-cell vertical">
                    <div class="wx-cell-top">
                        <span class="wx-tag ${catCls}">${a.category}</span>
                        ${a.pinned ? '<span class="wx-tag pin">置顶</span>' : ''}
                        <span class="wx-cell-time">${a.created_at || ''}</span>
                    </div>
                    <span class="wx-cell-title">${a.title}</span>
                    <span class="wx-cell-desc">${a.content}</span>
                </div>
            `;
        }).join('')}</div>`;
    } catch(e) {
        container.innerHTML = '<div class="wx-empty">加载失败</div>';
    }
}

async function loadMyAssignments() {
    const container = document.getElementById('wx-assignments-list');
    if (!container) return;
    const userId = AppState.currentUser?.id || AppState.sessionId || '';
    try {
        const data = await apiCall(`/api/student/submissions?user_id=${userId}`);
        if (!data.success || !data.submissions.length) {
            container.innerHTML = '<div class="wx-empty"><i class="fas fa-file-lines"></i><p>暂无作业记录</p></div>';
            return;
        }
        container.innerHTML = `<div class="wx-cell-group">${data.submissions.map(s => {
            const statusMap = { 'pending': '待批改', 'graded': '已批改' };
            const statusCls = s.status === 'graded' ? 'green' : 'orange';
            const scoreText = s.score != null ? `${s.score}分` : '';
            return `
                <div class="wx-cell vertical">
                    <div class="wx-cell-top">
                        <span class="wx-cell-title">${s.assignment_title || '作业'}</span>
                        <span class="wx-tag ${statusCls}">${statusMap[s.status] || s.status}</span>
                    </div>
                    <div class="wx-cell-meta">
                        ${scoreText ? `<span>得分：<strong>${scoreText}</strong></span>` : ''}
                        ${s.feedback ? `<span>评语：${s.feedback}</span>` : ''}
                        <span>${s.submitted_at || ''}</span>
                    </div>
                </div>
            `;
        }).join('')}</div>`;
    } catch(e) {
        container.innerHTML = '<div class="wx-empty">加载失败</div>';
    }
}

async function loadMyAttendance() {
    const container = document.getElementById('wx-attendance-list');
    if (!container) return;
    const userId = AppState.currentUser?.id || AppState.sessionId || '';
    try {
        const data = await apiCall(`/api/student/attendance?user_id=${userId}`);
        if (!data.success || !data.records.length) {
            container.innerHTML = '<div class="wx-empty"><i class="fas fa-clipboard-check"></i><p>暂无考勤记录</p></div>';
            return;
        }
        // 统计
        const total = data.records.length;
        const present = data.records.filter(r => r.check_status === 'present').length;
        const late = data.records.filter(r => r.check_status === 'late').length;
        const absent = data.records.filter(r => !r.check_status).length;
        const rate = total ? (present / total * 100).toFixed(0) : 0;

        container.innerHTML = `
            <div class="wx-attendance-stats">
                <div class="wx-att-stat"><span class="wx-att-num">${total}</span><span class="wx-att-label">总签到</span></div>
                <div class="wx-att-stat"><span class="wx-att-num green">${present}</span><span class="wx-att-label">已签到</span></div>
                <div class="wx-att-stat"><span class="wx-att-num orange">${late}</span><span class="wx-att-label">迟到</span></div>
                <div class="wx-att-stat"><span class="wx-att-num red">${absent}</span><span class="wx-att-label">缺勤</span></div>
                <div class="wx-att-stat"><span class="wx-att-num blue">${rate}%</span><span class="wx-att-label">出勤率</span></div>
            </div>
            <div class="wx-cell-group">${data.records.map(r => {
                const statusMap = { 'present': '已签到', 'late': '迟到' };
                const statusCls = r.check_status === 'present' ? 'green' : r.check_status === 'late' ? 'orange' : 'red';
                const statusText = statusMap[r.check_status] || '缺勤';
                return `
                    <div class="wx-cell">
                        <span class="wx-cell-label">${r.title || '签到'}</span>
                        <span class="wx-cell-time">${r.session_time || ''}</span>
                        <span class="wx-tag ${statusCls}">${statusText}</span>
                    </div>
                `;
            }).join('')}</div>`;
    } catch(e) {
        container.innerHTML = '<div class="wx-empty">加载失败</div>';
    }
}

// ==================== 农产品选择 ====================

function setupProductSelection() {
    setupSelectionHandler('.product-card', 'active', 'currentProduct', () => updateFarmingCalendar());
}

// ==================== 手工艺选择 ====================

function setupCraftSelection() {
    setupSelectionHandler('.craft-card', 'active', 'currentCraft', () => updateCraftSteps());
}

async function updateCraftSteps() {
    const container = document.getElementById('craft-steps');
    const materialsGrid = document.querySelector('.materials-grid');
    if (!container) return;
    showSkeleton(container, 'text', 4);

    try {
        const data = await apiCall(`/api/crafts/${AppState.currentCraft}`);
        if (data.success && data.data) {
            // 渲染步骤
            if (data.data.steps && data.data.steps.length > 0) {
                container.innerHTML = data.data.steps.map((s, i) => `
                    <div class="step${i === 0 ? ' active' : ''}">
                        <span class="step-number">${i + 1}</span>
                        <div class="step-content">
                            <h5>${s.title}</h5>
                            <p>${s.desc}</p>
                            ${s.tips ? `<div class="step-tips"><i class="fas fa-lightbulb"></i> ${s.tips}</div>` : ''}
                        </div>
                    </div>
                `).join('');
            } else {
                showEmptyState(container, 'fa-paint-brush', '暂无步骤', '该手工艺的步骤正在准备中');
            }

            // 渲染材料采购指南
            if (materialsGrid && data.data.materials && data.data.materials.length > 0) {
                materialsGrid.innerHTML = data.data.materials.map(m => `
                    <div class="material-card">
                        <div class="material-icon"><i class="fas fa-tools"></i></div>
                        <h4>${m.name}</h4>
                        <p>${m.note || ''}</p>
                        <span class="price-tag">${m.price}</span>
                        ${m.where ? `<div class="material-where"><i class="fas fa-map-marker-alt"></i> ${m.where}</div>` : ''}
                    </div>
                `).join('');
            }
        }
    } catch(e) {
        showErrorState(container, '加载手工艺步骤失败', () => updateCraftSteps());
    }
}

// ==================== 方言选择 ====================

const VoiceState = {
    history: [],
    maxHistory: 10,
    isRecording: false,
    recognition: null
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
            VoiceState.isRecording = true;
            voiceBtn.classList.add('recording');
            setTimeout(() => {
                stopRecording();
                sendVoiceMessage('请问荔枝什么时候施肥最好？');
            }, 2000);
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
        VoiceState.history = [];
        const messages = document.getElementById('voice-chat-messages');
        if (messages) {
            messages.innerHTML = `<div class="voice-welcome"><i class="fas fa-robot"></i><p>你好！我是方言农业助手，可以用普通话或方言向我提问</p></div>`;
        }
    });

    // 加载默认方言信息
    loadDialectInfo(AppState.currentDialect || 'cantonese');
}

function startSpeechRecognition() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    const recognition = new SpeechRecognition();
    recognition.lang = 'zh-CN';
    recognition.interimResults = true;
    recognition.continuous = false;
    VoiceState.recognition = recognition;
    VoiceState.isRecording = true;

    const voiceBtn = document.getElementById('voice-record-btn');
    voiceBtn?.classList.add('recording');

    recognition.onresult = function(event) {
        const transcript = event.results[0][0].transcript;
        const textInput = document.getElementById('voice-text-input');
        if (textInput) textInput.value = transcript;
        if (event.results[0].isFinal) {
            sendVoiceMessage(transcript);
            if (textInput) textInput.value = '';
        }
    };

    recognition.onerror = function() {
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

async function loadDialectInfo(dialectId) {
    try {
        const data = await apiCall(`/api/resources/dialect-info?dialect=${dialectId}`);
        if (data.success && data.info) {
            renderDialectInfo(data.info);
        }
    } catch(e) {
        // 静默失败
    }
}

function renderDialectInfo(info) {
    // 问候语
    const greetingMain = document.getElementById('greeting-main');
    const greetingMeaning = document.getElementById('greeting-meaning');
    if (greetingMain) greetingMain.textContent = info.greeting || '';
    if (greetingMeaning) greetingMeaning.textContent = `（${info.greeting_meaning || ''}）`;

    // 特征标签
    const featuresEl = document.getElementById('dialect-features');
    if (featuresEl && info.features) {
        featuresEl.innerHTML = info.features.map(f => `<span class="feature-tag">${f}</span>`).join('');
    }

    // 常用短语
    const phrasesGrid = document.getElementById('phrases-grid');
    if (phrasesGrid && info.phrases) {
        phrasesGrid.innerHTML = info.phrases.map(p =>
            `<div class="phrase-item" data-text="${p.dialect}" title="点击发送：${p.dialect}">
                <span class="phrase-dialect">${p.dialect}</span>
                <span class="phrase-mandarin">${p.mandarin}</span>
                <span class="phrase-pinyin">${p.pinyin || ''}</span>
            </div>`
        ).join('');
        // 点击短语发送
        phrasesGrid.querySelectorAll('.phrase-item').forEach(item => {
            item.addEventListener('click', () => {
                sendVoiceMessage(item.dataset.text);
            });
        });
    }

    // 快捷问题
    const quickEl = document.getElementById('voice-quick-questions');
    if (quickEl && info.quick_questions) {
        quickEl.innerHTML = info.quick_questions.map(q =>
            `<button class="voice-quick-btn">${q}</button>`
        ).join('');
        quickEl.querySelectorAll('.voice-quick-btn').forEach(btn => {
            btn.addEventListener('click', () => sendVoiceMessage(btn.textContent));
        });
    }
}

async function sendVoiceMessage(text) {
    const messagesEl = document.getElementById('voice-chat-messages');
    if (!messagesEl) return;

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
            html += `<div>${formatAnswer(r.answer || '暂无回答')}</div>`;
            if (r.suggestions && r.suggestions.length) {
                html += `<div class="msg-suggestions">${r.suggestions.map(s =>
                    `<span class="suggestion-btn">${s}</span>`
                ).join('')}</div>`;
            }
            botMsg.innerHTML = html;
            messagesEl.appendChild(botMsg);

            // 追问按钮点击
            botMsg.querySelectorAll('.suggestion-btn').forEach(btn => {
                btn.addEventListener('click', () => sendVoiceMessage(btn.textContent));
            });

            // 保存历史
            VoiceState.history.push({ user: text, bot: r.answer });
            if (VoiceState.history.length > VoiceState.maxHistory) {
                VoiceState.history = VoiceState.history.slice(-VoiceState.maxHistory);
            }
        }
    } catch(e) {
        loadingMsg.remove();
        const errMsg = document.createElement('div');
        errMsg.className = 'voice-msg bot';
        errMsg.textContent = '抱歉，暂时无法回答，请稍后再试';
        messagesEl.appendChild(errMsg);
    }

    messagesEl.scrollTop = messagesEl.scrollHeight;
}

// ==================== 农业问答（对话式） ====================

const QAState = {
    history: [],
    maxHistory: 10,
    lastAnswer: '',
    isTyping: false
};

function setupAgricultureQA() {
    const askBtn = document.getElementById('ask-agriculture-btn');
    const questionInput = document.getElementById('agriculture-question');
    const clearBtn = document.getElementById('qa-clear-btn');

    askBtn?.addEventListener('click', () => {
        const question = questionInput.value.trim();
        if (!question || QAState.isTyping) return;
        questionInput.value = '';
        autoResizeTextarea(questionInput);
        askAgricultureQuestion(question);
    });

    questionInput?.addEventListener('keydown', e => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            askBtn?.click();
        }
    });

    // 自动调整文本框高度
    questionInput?.addEventListener('input', () => autoResizeTextarea(questionInput));

    clearBtn?.addEventListener('click', () => {
        QAState.history = [];
        QAState.lastAnswer = '';
        const flow = document.getElementById('qa-chat-flow');
        if (flow) {
            flow.innerHTML = `
                <div class="qa-welcome">
                    <i class="fas fa-robot"></i>
                    <p>你好！我是AI农技专家，专注于<strong id="qa-product-label">${getProductName(AppState.currentProduct)}</strong>种植指导。有什么问题尽管问我！</p>
                </div>
            `;
        }
    });

    // 示例问题（动态 + 静态混合）
    bindSuggestionClicks();

    // 农产品切换时刷新建议
    const origSwitch = AppState.currentProduct;
    const observer = new MutationObserver(() => {
        if (AppState.currentProduct !== origSwitch) {
            QAState.history = [];
            refreshSuggestions(AppState.currentProduct);
            updateProductLabel();
            clearChatFlow();
        }
    });
    // 监听产品选择变化
    document.querySelectorAll('.product-card').forEach(card => {
        card.addEventListener('click', () => {
            setTimeout(() => {
                refreshSuggestions(AppState.currentProduct);
                updateProductLabel();
            }, 50);
        });
    });
}

function autoResizeTextarea(el) {
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 100) + 'px';
}

function getProductName(productId) {
    const names = { lychee: '荔枝', longan: '龙眼', aquatic: '水产养殖', rice: '水稻', tea: '茶叶', vegetable: '蔬菜' };
    return names[productId] || '广东特色农产品';
}

function updateProductLabel() {
    const label = document.getElementById('qa-product-label');
    if (label) label.textContent = getProductName(AppState.currentProduct);
}

function clearChatFlow() {
    const flow = document.getElementById('qa-chat-flow');
    if (flow) {
        flow.innerHTML = `
            <div class="qa-welcome">
                <i class="fas fa-robot"></i>
                <p>你好！我是AI农技专家，专注于<strong>${getProductName(AppState.currentProduct)}</strong>种植指导。有什么问题尽管问我！</p>
            </div>
        `;
    }
}

function bindSuggestionClicks() {
    const container = document.getElementById('qa-suggestions');
    if (!container) return;
    container.addEventListener('click', e => {
        const btn = e.target.closest('.example-btn');
        if (!btn) return;
        const q = btn.dataset.question || btn.textContent;
        const input = document.getElementById('agriculture-question');
        if (input) input.value = '';
        askAgricultureQuestion(q);
    });
}

async function refreshSuggestions(product) {
    try {
        const data = await apiCall(`/api/agriculture/suggestions?product=${product}`);
        if (data.success && data.suggestions) {
            const container = document.getElementById('qa-suggestions');
            if (container) {
                container.innerHTML = data.suggestions.map(q =>
                    `<button class="example-btn" data-question="${q}">${q}</button>`
                ).join('');
            }
        }
    } catch (e) {
        // 静默失败，保留原有建议
    }
}

function appendMessage(role, content) {
    const flow = document.getElementById('qa-chat-flow');
    if (!flow) return;

    // 移除欢迎信息
    const welcome = flow.querySelector('.qa-welcome');
    if (welcome) welcome.remove();

    const div = document.createElement('div');
    div.className = `qa-message ${role}`;

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

function appendSuggestions(suggestions) {
    const flow = document.getElementById('qa-chat-flow');
    if (!flow || !suggestions || suggestions.length === 0) return;

    const div = document.createElement('div');
    div.className = 'qa-msg-suggestions';
    div.innerHTML = `
        <div class="qa-msg-actions" style="margin-top:4px;">
            ${suggestions.map(q =>
                `<button class="qa-action-btn suggest-btn" data-question="${escapeHtml(q)}"><i class="fas fa-reply"></i> ${escapeHtml(q)}</button>`
            ).join('')}
        </div>
    `;
    flow.appendChild(div);

    div.querySelectorAll('.suggest-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            askAgricultureQuestion(btn.dataset.question);
        });
    });

    flow.scrollTop = flow.scrollHeight;
}

function appendActions(answer) {
    const flow = document.getElementById('qa-chat-flow');
    if (!flow) return;

    const div = document.createElement('div');
    div.className = 'qa-msg-actions';
    div.innerHTML = `
        <button class="qa-action-btn copy-btn"><i class="fas fa-copy"></i> 复制</button>
        <button class="qa-action-btn retry-btn"><i class="fas fa-redo"></i> 重新生成</button>
    `;
    flow.appendChild(div);

    div.querySelector('.copy-btn')?.addEventListener('click', function() {
        navigator.clipboard.writeText(answer).then(() => {
            this.classList.add('copied');
            this.innerHTML = '<i class="fas fa-check"></i> 已复制';
            setTimeout(() => {
                this.classList.remove('copied');
                this.innerHTML = '<i class="fas fa-copy"></i> 复制';
            }, 2000);
        });
    });

    div.querySelector('.retry-btn')?.addEventListener('click', () => {
        if (QAState.history.length > 0) {
            const last = QAState.history[QAState.history.length - 1];
            QAState.history.pop();
            // 移除最后一条bot消息和actions
            const messages = flow.querySelectorAll('.qa-message');
            const lastMsg = messages[messages.length - 1];
            if (lastMsg?.classList.contains('bot')) lastMsg.remove();
            div.remove();
            // 移除追问建议
            const suggestions = flow.querySelector('.qa-msg-suggestions');
            if (suggestions) suggestions.remove();
            askAgricultureQuestion(last.question);
        }
    });

    flow.scrollTop = flow.scrollHeight;
}

async function askAgricultureQuestion(question) {
    if (QAState.isTyping) return;
    QAState.isTyping = true;

    appendMessage('user', question);

    // 优先使用 SSE 流式，失败回退到普通请求
    const streamOk = await askAgricultureStreaming(question);
    if (streamOk) {
        QAState.isTyping = false;
        return;
    }

    // 流式失败，回退到传统请求
    const typingEl = appendTypingIndicator();

    try {
        const data = await apiCall('/api/agriculture/ask', 'POST', {
            question,
            product: AppState.currentProduct,
            history: QAState.history.slice(-5)
        });

        removeTypingIndicator();

        if (data.success) {
            const answer = data.answer;
            QAState.lastAnswer = answer;

            // 添加到历史
            QAState.history.push({ question, answer });
            if (QAState.history.length > QAState.maxHistory) QAState.history.shift();

            // 渲染回答（打字机效果）
            const msg = appendMessage('bot', '');
            const contentEl = msg.querySelector('.msg-content');
            await typewriterEffect(contentEl, answer);
            contentEl.innerHTML = formatAnswer(answer);

            // 操作按钮
            appendActions(answer);

            // 追问建议
            if (data.suggestions && data.suggestions.length > 0) {
                appendSuggestions(data.suggestions);
            }

            // 更新底部建议
            refreshSuggestions(AppState.currentProduct);
        }
    } catch (e) {
        removeTypingIndicator();
        const msg = appendMessage('bot', '');
        const contentEl = msg.querySelector('.msg-content');
        showErrorState(contentEl, 'AI服务暂时不可用，请稍后重试', () => {
            QAState.history.pop();
            askAgricultureQuestion(question);
        });
    } finally {
        QAState.isTyping = false;
    }
}

// ==================== SSE 流式 AI 问答 ====================

async function askAgricultureStreaming(question) {
    try {
        const response = await fetch(`${API_BASE_URL}/api/agriculture/ask/stream`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...(AppState.sessionId ? { 'X-Session-Id': AppState.sessionId } : {})
            },
            body: JSON.stringify({
                question,
                product: AppState.currentProduct,
                history: QAState.history.slice(-5)
            })
        });

        if (!response.ok) return false;

        const msg = appendMessage('bot', '');
        const contentEl = msg.querySelector('.msg-content');
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let fullAnswer = '';
        const flow = document.getElementById('qa-chat-flow');

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.slice(6));
                        fullAnswer += data.content;
                        contentEl.innerHTML = formatAnswer(fullAnswer);
                        if (flow) flow.scrollTop = flow.scrollHeight;
                    } catch (e) { /* 跳过解析失败的行 */ }
                } else if (line.startsWith('event: error')) {
                    return false;
                }
            }
        }

        // 流式完成
        QAState.lastAnswer = fullAnswer;
        QAState.history.push({ question, answer: fullAnswer });
        if (QAState.history.length > QAState.maxHistory) QAState.history.shift();
        contentEl.innerHTML = formatAnswer(fullAnswer);

        // 操作按钮
        appendActions(fullAnswer);

        // 更新底部建议
        refreshSuggestions(AppState.currentProduct);

        return true;
    } catch (e) {
        console.warn('SSE流式失败，回退到普通请求:', e.message);
        return false;
    }
}

function escapeHtml(text) {
    const d = document.createElement('div');
    d.textContent = text;
    return d.innerHTML;
}

function formatAnswer(text) {
    // 简单markdown-like格式化
    return text
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\n/g, '<br>')
        .replace(/(\d+)\./g, '<br>$1.')
        .replace(/- /g, '<br>- ');
}

// ==================== 农时日历 ====================

function setupCalendar() {
    document.getElementById('prev-month')?.addEventListener('click', () => {
        AppState.calendarMonth--;
        if (AppState.calendarMonth < 0) { AppState.calendarMonth = 11; AppState.calendarYear--; }
        updateFarmingCalendar();
    });

    document.getElementById('next-month')?.addEventListener('click', () => {
        AppState.calendarMonth++;
        if (AppState.calendarMonth > 11) { AppState.calendarMonth = 0; AppState.calendarYear++; }
        updateFarmingCalendar();
    });

    updateFarmingCalendar();
}

function updateFarmingCalendar() {
    const calendarGrid = document.getElementById('calendar-grid');
    const taskList = document.getElementById('farming-task-list');
    const monthLabel = document.getElementById('current-month');
    if (!calendarGrid) return;

    const year = AppState.calendarYear;
    const month = AppState.calendarMonth;
    const today = new Date();

    if (monthLabel) monthLabel.textContent = `${year}年${month + 1}月`;

    // 生成日历
    let html = '';
    const days = ['日', '一', '二', '三', '四', '五', '六'];
    days.forEach(d => {
        html += `<div class="calendar-header">${d}</div>`;
    });

    const firstDay = new Date(year, month, 1).getDay();
    const daysInMonth = new Date(year, month + 1, 0).getDate();

    // 填充前置空格
    for (let i = 0; i < firstDay; i++) html += '<div class="calendar-day"></div>';

    // 有农事任务的日期
    const taskDays = [5, 10, 15, 20, 25];
    for (let d = 1; d <= daysInMonth; d++) {
        const isToday = (d === today.getDate() && month === today.getMonth() && year === today.getFullYear());
        const hasTask = taskDays.includes(d);
        const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
        const term = SOLAR_TERMS[dateStr];
        let cls = 'calendar-day';
        if (hasTask) cls += ' has-task';
        if (isToday) cls += ' today';
        const marker = term ? `<span class="lunar-marker">${term}</span>` : '';
        html += `<div class="${cls}">${d}${marker}</div>`;
    }
    calendarGrid.innerHTML = html;

    // 更新农事任务
    if (taskList) {
        const month = AppState.calendarMonth; // 0-indexed
        const tasks = getFarmingTasks(AppState.currentProduct, month);
        taskList.innerHTML = tasks.map((t, i) => {
            const colors = { fertilize: '#10b981', pest: '#ef4444', harvest: '#f59e0b', manage: '#3b82f6', water: '#06b6d4' };
            const color = colors[t.category] || colors.manage;
            return `
            <div class="task-item task-item-rich" style="--task-color: ${color}" data-idx="${i}">
                <div class="task-header">
                    <div class="task-icon-wrap" style="background: ${color}15; color: ${color}">
                        <i class="fas ${t.icon}"></i>
                    </div>
                    <div class="task-meta">
                        <h5>${t.title}</h5>
                        <div class="task-tags">
                            <span class="task-tag tag-category" style="background: ${color}18; color: ${color}">${t.categoryLabel}</span>
                            ${t.priority === 'high' ? '<span class="task-tag tag-urgent"><i class="fas fa-fire"></i> 紧急</span>' : ''}
                            <span class="task-tag tag-timing"><i class="far fa-clock"></i> ${t.timing}</span>
                        </div>
                    </div>
                    <button class="task-expand-btn" aria-label="展开详情"><i class="fas fa-chevron-down"></i></button>
                </div>
                <p class="task-desc">${t.description}</p>
                <div class="task-detail">
                    <div class="task-tips">
                        <i class="fas fa-lightbulb"></i>
                        <span>${t.tip}</span>
                    </div>
                </div>
            </div>
            `;
        }).join('');

        // 展开/折叠
        taskList.querySelectorAll('.task-expand-btn').forEach(btn => {
            btn.addEventListener('click', function() {
                const item = this.closest('.task-item-rich');
                item.classList.toggle('expanded');
            });
        });
    }
}

function getFarmingTasks(product, month) {
    const monthNames = ['一月','二月','三月','四月','五月','六月','七月','八月','九月','十月','十一月','十二月'];
    const timing = (m) => monthNames[m] || monthNames[month];

    const allTasks = {
        lychee: {
            0: [
                { title: '冬季清园', icon: 'broom', category: 'manage', categoryLabel: '管理', priority: 'high', timing: timing(0), description: '清除落叶、病枝，集中烧毁，减少越冬病虫源', tip: '清园后喷施3-5波美度石硫合剂，杀灭越冬病菌' },
                { title: '树干涂白', icon: 'paint-roller', category: 'manage', categoryLabel: '管理', priority: 'medium', timing: timing(0), description: '用石灰水涂白树干，防冻防虫', tip: '涂白高度至第一主枝，石灰中可加入少量硫磺粉' }
            ],
            1: [
                { title: '促花肥施用', icon: 'seedling', category: 'fertilize', categoryLabel: '施肥', priority: 'high', timing: timing(1), description: '施用速效磷钾肥，促进花芽分化', tip: '每株施复合肥0.5-1公斤，配合有机肥效果更佳' },
                { title: '花前病虫害预防', icon: 'shield-virus', category: 'pest', categoryLabel: '植保', priority: 'high', timing: timing(1), description: '重点防治霜疫霉病、荔枝蝽蟓', tip: '花前喷施一次杀菌剂+杀虫剂组合' }
            ],
            2: [
                { title: '花期管理', icon: 'spa', category: 'manage', categoryLabel: '管理', priority: 'high', timing: timing(2), description: '放蜂授粉，遇连续阴雨需人工辅助授粉', tip: '花期忌喷农药，如需防治请在花前完成' },
                { title: '保花保果', icon: 'hand-holding-heart', category: 'fertilize', categoryLabel: '施肥', priority: 'medium', timing: timing(2), description: '喷施磷酸二氢钾+硼肥，提高坐果率', tip: '浓度0.2%磷酸二氢钾+0.1%硼砂，花期喷2次' }
            ],
            3: [
                { title: '果实膨大期', icon: 'apple-alt', category: 'fertilize', categoryLabel: '施肥', priority: 'high', timing: timing(3), description: '施壮果肥，保持充足水分供应', tip: '每株施硫酸钾0.5公斤，配合灌水' },
                { title: '蒂蛀虫防治', icon: 'bug', category: 'pest', categoryLabel: '植保', priority: 'high', timing: timing(3), description: '果实发育期重点防治蒂蛀虫', tip: '成虫羽化高峰期喷药，选用高效氯氰菊酯' }
            ],
            4: [
                { title: '果实转色管理', icon: 'palette', category: 'manage', categoryLabel: '管理', priority: 'medium', timing: timing(4), description: '控制氮肥，增施钾肥促进着色', tip: '转色期减少灌水，提高果实甜度' },
                { title: '排水防裂果', icon: 'tint', category: 'water', categoryLabel: '水分', priority: 'high', timing: timing(4), description: '果实成熟期遇暴雨易裂果，注意排水', tip: '雨后及时排水，可覆盖地膜减少水分波动' }
            ],
            5: [
                { title: '荔枝采收', icon: 'shopping-basket', category: 'harvest', categoryLabel: '采收', priority: 'high', timing: timing(5), description: '适时采收成熟果实，分批采摘', tip: '果皮转红2/3时采收，保留果穗枝保证品质' },
                { title: '采后修剪', icon: 'cut', category: 'manage', categoryLabel: '管理', priority: 'high', timing: timing(5), description: '采果后进行回缩修剪，保持树冠通风', tip: '修剪量不超过树冠的1/3，保留内膛枝' }
            ],
            6: [
                { title: '施用恢复肥', icon: 'fill-drip', category: 'fertilize', categoryLabel: '施肥', priority: 'high', timing: timing(6), description: '采果后重施有机肥，恢复树势', tip: '每株施有机肥10-20公斤+复合肥1公斤' },
                { title: '秋梢管理', icon: 'tree', category: 'manage', categoryLabel: '管理', priority: 'medium', timing: timing(6), description: '培养健壮秋梢，为来年结果打基础', tip: '统一放梢，抹除零星早发的芽' }
            ],
            7: [
                { title: '秋梢病虫防治', icon: 'shield-virus', category: 'pest', categoryLabel: '植保', priority: 'medium', timing: timing(7), description: '保护新梢，防治尺蠖、卷叶蛾', tip: '新梢萌发1-2厘米时喷第一次药' },
                { title: '水分管理', icon: 'tint', category: 'water', categoryLabel: '水分', priority: 'medium', timing: timing(7), description: '秋梢生长期保持充足水分', tip: '干旱时及时灌水，每7-10天一次' }
            ],
            8: [
                { title: '控梢促花', icon: 'hand-paper', category: 'manage', categoryLabel: '管理', priority: 'high', timing: timing(8), description: '末次秋梢老熟后开始控梢', tip: '可采用环割或喷施控梢药剂' },
                { title: '深翻改土', icon: 'mountain', category: 'manage', categoryLabel: '管理', priority: 'low', timing: timing(8), description: '结合施有机肥进行深翻改土', tip: '深翻30-40厘米，断根促发新根' }
            ],
            9: [
                { title: '花芽分化期', icon: 'seedling', category: 'fertilize', categoryLabel: '施肥', priority: 'high', timing: timing(9), description: '控制氮肥，增施磷钾肥促进花芽分化', tip: '叶面喷施0.3%磷酸二氢钾' },
                { title: '冬季清园准备', icon: 'broom', category: 'manage', categoryLabel: '管理', priority: 'low', timing: timing(9), description: '清理果园杂草，准备冬季管理', tip: '清除园内杂草和落叶，减少病虫越冬场所' }
            ],
            10: [
                { title: '冬季修剪', icon: 'cut', category: 'manage', categoryLabel: '管理', priority: 'medium', timing: timing(10), description: '疏除过密枝、交叉枝、病虫枝', tip: '修剪后涂抹伤口愈合剂' },
                { title: '防寒措施', icon: 'snowflake', category: 'manage', categoryLabel: '管理', priority: 'medium', timing: timing(10), description: '幼树覆盖防寒，树盘覆草', tip: '低温来临前树冠覆盖薄膜' }
            ],
            11: [
                { title: '冬季清园', icon: 'broom', category: 'manage', categoryLabel: '管理', priority: 'high', timing: timing(11), description: '全面清园，喷施石硫合剂', tip: '落叶后全园喷施3-5波美度石硫合剂' },
                { title: '施基肥', icon: 'fill-drip', category: 'fertilize', categoryLabel: '施肥', priority: 'medium', timing: timing(11), description: '深施有机肥改良土壤', tip: '沿树冠滴水线开沟施肥，深度30-40厘米' }
            ]
        },
        longan: {
            0: [{ title: '冬季管理', icon: 'snowflake', category: 'manage', categoryLabel: '管理', priority: 'medium', timing: timing(0), description: '清园修剪，防寒防冻', tip: '喷施石硫合剂清园' }],
            1: [{ title: '促花肥', icon: 'seedling', category: 'fertilize', categoryLabel: '施肥', priority: 'high', timing: timing(1), description: '施磷钾肥促花', tip: '每株施复合肥0.5公斤' }],
            2: [{ title: '花穗管理', icon: 'spa', category: 'manage', categoryLabel: '管理', priority: 'high', timing: timing(2), description: '疏花穗，去除弱花', tip: '保留60-70%花穗' }],
            3: [{ title: '保果措施', icon: 'hand-holding-heart', category: 'fertilize', categoryLabel: '施肥', priority: 'high', timing: timing(3), description: '喷施保果药剂', tip: '谢花后喷九二零+磷酸二氢钾' }],
            4: [{ title: '果实膨大', icon: 'apple-alt', category: 'fertilize', categoryLabel: '施肥', priority: 'high', timing: timing(4), description: '加强水肥管理', tip: '施壮果肥，保持水分' }],
            5: [{ title: '龙眼采收', icon: 'shopping-basket', category: 'harvest', categoryLabel: '采收', priority: 'high', timing: timing(5), description: '适时采收', tip: '果壳转黄、果肉饱满时采收' }],
            6: [{ title: '采后管理', icon: 'cut', category: 'manage', categoryLabel: '管理', priority: 'high', timing: timing(6), description: '修剪+施恢复肥', tip: '采后尽快施肥恢复树势' }],
            7: [{ title: '秋梢管理', icon: 'tree', category: 'manage', categoryLabel: '管理', priority: 'medium', timing: timing(7), description: '培养健壮秋梢', tip: '统一放梢，防治新梢害虫' }],
            8: [{ title: '控梢', icon: 'hand-paper', category: 'manage', categoryLabel: '管理', priority: 'high', timing: timing(8), description: '控制冬梢萌发', tip: '环割或喷控梢药剂' }],
            9: [{ title: '花芽分化', icon: 'seedling', category: 'fertilize', categoryLabel: '施肥', priority: 'medium', timing: timing(9), description: '促进花芽分化', tip: '控氮增磷钾' }],
            10: [{ title: '冬季修剪', icon: 'cut', category: 'manage', categoryLabel: '管理', priority: 'medium', timing: timing(10), description: '修剪整形', tip: '疏除密枝病枝' }],
            11: [{ title: '清园施肥', icon: 'broom', category: 'manage', categoryLabel: '管理', priority: 'high', timing: timing(11), description: '冬季清园+施基肥', tip: '有机肥深施改土' }]
        },
        aquatic: {
            0: [{ title: '越冬管理', icon: 'snowflake', category: 'manage', categoryLabel: '管理', priority: 'high', timing: timing(0), description: '保持水温，减少投喂', tip: '加深水位至2米以上保温' }],
            1: [{ title: '清塘消毒', icon: 'broom', category: 'manage', categoryLabel: '管理', priority: 'high', timing: timing(1), description: '干塘暴晒，生石灰消毒', tip: '每亩用生石灰75-100公斤' }],
            2: [{ title: '放苗准备', icon: 'fish', category: 'manage', categoryLabel: '管理', priority: 'high', timing: timing(2), description: '培水、试水、放苗', tip: '水温稳定15℃以上再放苗' }],
            3: [{ title: '水质调控', icon: 'tint', category: 'water', categoryLabel: '水分', priority: 'high', timing: timing(3), description: '保持水质稳定', tip: '每7-10天换水一次，每次换1/3' }],
            4: [{ title: '投喂管理', icon: 'utensils', category: 'manage', categoryLabel: '管理', priority: 'medium', timing: timing(4), description: '根据天气调整投喂量', tip: '阴雨天减量或停喂' }],
            5: [{ title: '高温防缺氧', icon: 'temperature-high', category: 'water', categoryLabel: '水分', priority: 'high', timing: timing(5), description: '开启增氧机，预防泛塘', tip: '中午和凌晨各开增氧机2-3小时' }],
            6: [{ title: '病害高发防控', icon: 'shield-virus', category: 'pest', categoryLabel: '植保', priority: 'high', timing: timing(6), description: '高温期病害频发', tip: '定期消毒，拌喂大蒜素预防' }],
            7: [{ title: '轮捕轮放', icon: 'fishing', category: 'harvest', categoryLabel: '采收', priority: 'medium', timing: timing(7), description: '达到规格的及时捕捞', tip: '降低密度有利于剩余个体生长' }],
            8: [{ title: '秋季管理', icon: 'leaf', category: 'manage', categoryLabel: '管理', priority: 'medium', timing: timing(8), description: '调整投喂，预防秋瘟', tip: '水温下降时逐步减少投喂量' }],
            9: [{ title: '越冬准备', icon: 'snowflake', category: 'manage', categoryLabel: '管理', priority: 'high', timing: timing(9), description: '加深水位，减少操作', tip: '达到商品规格的抓紧起捕上市' }],
            10: [{ title: '干塘起捕', icon: 'fishing', category: 'harvest', categoryLabel: '采收', priority: 'high', timing: timing(10), description: '年底干塘起捕', tip: '捕后清塘消毒准备来年' }],
            11: [{ title: '设备维护', icon: 'tools', category: 'manage', categoryLabel: '管理', priority: 'low', timing: timing(11), description: '维修增氧机、投饲机', tip: '利用空闲期检修养殖设备' }]
        },
        rice: {
            0: [{ title: '冬闲田管理', icon: 'mountain', category: 'manage', categoryLabel: '管理', priority: 'low', timing: timing(0), description: '翻耕冬闲田，晒田风化', tip: '深翻20-25厘米，利用低温杀灭越冬虫源' }],
            1: [{ title: '浸种催芽', icon: 'seedling', category: 'manage', categoryLabel: '管理', priority: 'high', timing: timing(1), description: '早稻浸种催芽', tip: '温水浸种48小时，保持30-35℃催芽' }],
            2: [{ title: '播种育秧', icon: 'seedling', category: 'manage', categoryLabel: '管理', priority: 'high', timing: timing(2), description: '适时播种，培育壮秧', tip: '秧田施足基肥，控制播种量' }],
            3: [{ title: '移栽', icon: 'exchange-alt', category: 'manage', categoryLabel: '管理', priority: 'high', timing: timing(3), description: '适时移栽，合理密植', tip: '株行距20×25厘米，每穴2-3苗' }],
            4: [{ title: '分蘖期管理', icon: 'tree', category: 'fertilize', categoryLabel: '施肥', priority: 'high', timing: timing(4), description: '追施分蘖肥，促进早发', tip: '移栽后7-10天追施尿素10公斤/亩' }],
            5: [{ title: '晒田控苗', icon: 'sun', category: 'water', categoryLabel: '水分', priority: 'high', timing: timing(5), description: '排水晒田，控制无效分蘖', tip: '田面出现鸡爪裂时复水' }],
            6: [{ title: '穗肥施用', icon: 'fill-drip', category: 'fertilize', categoryLabel: '施肥', priority: 'high', timing: timing(6), description: '幼穗分化期施穗肥', tip: '每亩施复合肥5-8公斤' }],
            7: [{ title: '稻飞虱防治', icon: 'bug', category: 'pest', categoryLabel: '植保', priority: 'high', timing: timing(7), description: '重点防治稻飞虱、纹枯病', tip: '选用吡蚜酮+井冈霉素组合' }],
            8: [{ title: '抽穗扬花', icon: 'spa', category: 'manage', categoryLabel: '管理', priority: 'medium', timing: timing(8), description: '保持浅水层，遇寒露风灌深水保温', tip: '喷施磷酸二氢钾提高结实率' }],
            9: [{ title: '灌浆结实', icon: 'apple-alt', category: 'water', categoryLabel: '水分', priority: 'medium', timing: timing(9), description: '干湿交替灌溉', tip: '收割前7天断水，便于机收' }],
            10: [{ title: '晚稻收割', icon: 'shopping-basket', category: 'harvest', categoryLabel: '采收', priority: 'high', timing: timing(10), description: '适时收割晚稻', tip: '九成黄时收割，减少落粒损失' }],
            11: [{ title: '稻草还田', icon: 'recycle', category: 'manage', categoryLabel: '管理', priority: 'low', timing: timing(11), description: '稻草粉碎还田改良土壤', tip: '配合施氮肥加速分解' }]
        },
        tea: {
            0: [{ title: '冬季封园', icon: 'snowflake', category: 'manage', categoryLabel: '管理', priority: 'high', timing: timing(0), description: '喷施石硫合剂封园', tip: '全园喷施0.5波美度石硫合剂' }],
            1: [{ title: '施催芽肥', icon: 'seedling', category: 'fertilize', categoryLabel: '施肥', priority: 'high', timing: timing(1), description: '施速效氮肥催芽', tip: '每亩施尿素15-20公斤' }],
            2: [{ title: '春茶准备', icon: 'mug-hot', category: 'manage', categoryLabel: '管理', priority: 'medium', timing: timing(2), description: '检修制茶设备，准备采摘', tip: '提前联系采茶工，春茶季用工紧张' }],
            3: [{ title: '春茶采摘', icon: 'hand-paper', category: 'harvest', categoryLabel: '采收', priority: 'high', timing: timing(3), description: '采摘一芽一叶或一芽二叶', tip: '晴天上午露水干后采摘品质最佳' }],
            4: [{ title: '茶园修剪', icon: 'cut', category: 'manage', categoryLabel: '管理', priority: 'medium', timing: timing(4), description: '春茶后轻修剪', tip: '剪去3-5厘米，促进夏芽萌发' }],
            5: [{ title: '夏茶管理', icon: 'temperature-high', category: 'manage', categoryLabel: '管理', priority: 'medium', timing: timing(5), description: '遮阳降温，防治虫害', tip: '覆盖遮阳网减少高温灼伤' }],
            6: [{ title: '小绿叶蝉防治', icon: 'bug', category: 'pest', categoryLabel: '植保', priority: 'high', timing: timing(6), description: '防治茶小绿叶蝉', tip: '黄板诱杀+生物农药防治' }],
            7: [{ title: '秋茶采摘', icon: 'hand-paper', category: 'harvest', categoryLabel: '采收', priority: 'medium', timing: timing(7), description: '采摘秋茶', tip: '秋茶香气好，可制作高香型茶' }],
            8: [{ title: '施基肥', icon: 'fill-drip', category: 'fertilize', categoryLabel: '施肥', priority: 'high', timing: timing(8), description: '重施有机基肥', tip: '沿树冠滴水线开沟深施' }],
            9: [{ title: '秋季修剪', icon: 'cut', category: 'manage', categoryLabel: '管理', priority: 'medium', timing: timing(9), description: '茶树深修剪或重修剪', tip: '衰老茶树可重度修剪更新' }],
            10: [{ title: '清园管理', icon: 'broom', category: 'manage', categoryLabel: '管理', priority: 'medium', timing: timing(10), description: '清理茶园杂草落叶', tip: '深翻土壤破坏害虫越冬场所' }],
            11: [{ title: '防寒防冻', icon: 'snowflake', category: 'manage', categoryLabel: '管理', priority: 'medium', timing: timing(11), description: '茶树根部培土覆盖', tip: '铺草覆盖保温保湿' }]
        },
        vegetable: {
            0: [{ title: '大棚育苗', icon: 'seedling', category: 'manage', categoryLabel: '管理', priority: 'high', timing: timing(0), description: '利用大棚培育早春蔬菜苗', tip: '保持棚内温度15-25℃' }],
            1: [{ title: '整地施基肥', icon: 'mountain', category: 'fertilize', categoryLabel: '施肥', priority: 'high', timing: timing(1), description: '深翻土地，施足基肥', tip: '每亩施有机肥2000-3000公斤' }],
            2: [{ title: '春季定植', icon: 'exchange-alt', category: 'manage', categoryLabel: '管理', priority: 'high', timing: timing(2), description: '瓜果类蔬菜定植', tip: '选择晴天下午定植，浇足定根水' }],
            3: [{ title: '田间管理', icon: 'leaf', category: 'manage', categoryLabel: '管理', priority: 'medium', timing: timing(3), description: '搭架引蔓、整枝打杈', tip: '及时搭架引蔓防止倒伏' }],
            4: [{ title: '病虫害防治', icon: 'shield-virus', category: 'pest', categoryLabel: '植保', priority: 'high', timing: timing(4), description: '防治蚜虫、白粉病', tip: '优先使用黄板+生物农药' }],
            5: [{ title: '夏季遮阳', icon: 'umbrella-beach', category: 'manage', categoryLabel: '管理', priority: 'high', timing: timing(5), description: '覆盖遮阳网降温', tip: '遮光率50-60%的遮阳网' }],
            6: [{ title: '灌溉管理', icon: 'tint', category: 'water', categoryLabel: '水分', priority: 'high', timing: timing(6), description: '早晚灌溉，避免中午浇水', tip: '滴灌或喷灌节水高效' }],
            7: [{ title: '秋播准备', icon: 'seedling', category: 'manage', categoryLabel: '管理', priority: 'medium', timing: timing(7), description: '准备秋播蔬菜种子和育苗', tip: '选择耐热品种进行秋播' }],
            8: [{ title: '秋季定植', icon: 'exchange-alt', category: 'manage', categoryLabel: '管理', priority: 'high', timing: timing(8), description: '叶菜类、根菜类定植', tip: '适当密植提高产量' }],
            9: [{ title: '采收上市', icon: 'shopping-basket', category: 'harvest', categoryLabel: '采收', priority: 'high', timing: timing(9), description: '秋季蔬菜大量上市', tip: '适时采收保证品质和口感' }],
            10: [{ title: '大棚蔬菜管理', icon: 'warehouse', category: 'manage', categoryLabel: '管理', priority: 'medium', timing: timing(10), description: '覆盖大棚膜，保温促长', tip: '注意通风排湿预防灰霉病' }],
            11: [{ title: '越冬蔬菜管理', icon: 'snowflake', category: 'manage', categoryLabel: '管理', priority: 'medium', timing: timing(11), description: '加强保温，减少通风', tip: '多层覆盖保温，寒潮时加温' }]
        }
    };

    const productTasks = allTasks[product] || allTasks.lychee;
    return productTasks[month] || productTasks[0] || [];
}

// ==================== 虚拟实训 ====================

function setupSimulationModules() {
    // 模块卡片点击
    document.querySelectorAll('.sim-module-card').forEach(module => {
        module.querySelector('.btn').addEventListener('click', function() {
            const simType = module.dataset.sim;
            // 关闭所有面板
            document.querySelectorAll('.sim-panel').forEach(p => p.classList.add('is-hidden'));
            const panel = document.getElementById(simType + '-area');
            if (panel) {
                panel.classList.remove('is-hidden');
                panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
            // 初始化对应模块
            if (simType === 'pest-diagnosis') initPestDiagnosis();
            else if (simType === 'live-practice') initLivePractice();
            else if (simType === 'craft-ar') initCraftAR();
        });
    });

    // 关闭按钮
    document.querySelectorAll('.sim-close-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const target = this.dataset.target;
            document.getElementById(target)?.classList.add('is-hidden');
        });
    });
}

// ==================== 病虫害诊断 ====================

const PestState = { selectedCrop: 'lychee', initialized: false };

function initPestDiagnosis() {
    if (PestState.initialized) return;
    PestState.initialized = true;

    // 作物选择
    document.querySelectorAll('.crop-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            document.querySelectorAll('.crop-btn').forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            PestState.selectedCrop = this.dataset.crop;
        });
    });

    // 开始诊断
    document.getElementById('start-diagnosis')?.addEventListener('click', runDiagnosis);

    // 上传照片
    document.getElementById('upload-photo-btn')?.addEventListener('click', () => {
        document.getElementById('plant-image')?.click();
    });
    document.getElementById('plant-image')?.addEventListener('change', function() {
        if (this.files.length > 0) runDiagnosis();
    });

    // 重新诊断
    document.getElementById('re-diagnose')?.addEventListener('click', () => {
        document.getElementById('diagnosis-result').classList.add('is-hidden');
        document.getElementById('symptom-text').value = '';
        document.getElementById('symptom-text').focus();
    });

    // 复制结果
    document.getElementById('copy-diagnosis')?.addEventListener('click', () => {
        const result = document.getElementById('diagnosis-result');
        if (result) {
            const text = result.innerText;
            navigator.clipboard.writeText(text).then(() => showNotification('诊断结果已复制', 'success'));
        }
    });
}

async function runDiagnosis() {
    const symptoms = document.getElementById('symptom-text')?.value?.trim() || '';
    showLoading('AI正在分析症状...');
    try {
        const data = await apiCall('/api/simulation/diagnose', 'POST', {
            crop: PestState.selectedCrop,
            symptoms: symptoms
        });
        hideLoading();
        if (data.success && data.diagnosis) {
            renderDiagnosis(data.diagnosis);
            showNotification('诊断完成！', 'success');
        }
    } catch(e) {
        hideLoading();
        showNotification('诊断服务暂时不可用', 'error');
    }
}

function renderDiagnosis(d) {
    // 病名
    const nameEl = document.getElementById('disease-name');
    if (nameEl) nameEl.textContent = (d.crop_icon || '') + ' ' + (d.disease || '待确认');

    // 严重程度
    const sevBadge = document.getElementById('severity-badge');
    if (sevBadge) {
        sevBadge.textContent = d.severity || '中度';
        sevBadge.dataset.level = d.severity || '中度';
    }

    // 置信度
    const pct = Math.round((d.confidence || 0.5) * 100);
    const confFill = document.getElementById('confidence-fill');
    const confText = document.getElementById('confidence-text');
    if (confFill) confFill.style.width = pct + '%';
    if (confText) confText.textContent = pct + '%';

    // 症状
    const symptomsList = document.getElementById('symptoms-list');
    if (symptomsList && d.symptoms) {
        symptomsList.innerHTML = d.symptoms.map(s => `<li>${s}</li>`).join('');
    }

    // 防治方案
    const treatList = document.getElementById('treatment-list');
    if (treatList && d.treatment) {
        treatList.innerHTML = d.treatment.map(t => `<li>${t}</li>`).join('');
    }

    // 预防措施
    const prevList = document.getElementById('prevention-list');
    if (prevList && d.prevention) {
        prevList.innerHTML = d.prevention.map(p => `<li>${p}</li>`).join('');
    }

    // 额外信息
    const timingText = document.getElementById('timing-text');
    if (timingText) timingText.textContent = d.timing || '发病初期';

    const noteText = document.getElementById('note-text');
    if (noteText) noteText.textContent = d.note || '';

    // 显示结果
    document.getElementById('diagnosis-result')?.classList.remove('is-hidden');
}

// ==================== 直播间实训 ====================

const PracticeState = { currentScenario: 'opening', initialized: false };

function initLivePractice() {
    if (PracticeState.initialized) return;
    PracticeState.initialized = true;

    // 场景卡片点击
    document.querySelectorAll('.scenario-card').forEach(card => {
        card.addEventListener('click', function() {
            document.querySelectorAll('.scenario-card').forEach(c => c.classList.remove('active'));
            this.classList.add('active');
            PracticeState.currentScenario = this.dataset.scenario;
            loadScenario(PracticeState.currentScenario);
        });
    });

    // 提示标签点击填充
    document.addEventListener('click', function(e) {
        if (e.target.classList.contains('prompt-tag')) {
            const textarea = document.getElementById('practice-text');
            if (textarea) {
                textarea.value = e.target.textContent;
                textarea.focus();
            }
        }
    });

    // AI评分
    document.getElementById('score-practice')?.addEventListener('click', scorePractice);

    // 清空
    document.getElementById('clear-practice')?.addEventListener('click', () => {
        document.getElementById('practice-text').value = '';
        document.getElementById('practice-score')?.classList.add('is-hidden');
    });

    loadScenario('opening');
}

function loadScenario(scenarioId) {
    const scenarios = {
        opening: { desc: '练习如何在30秒内抓住观众注意力', prompts: ['请用一句话欢迎观众并介绍今天的产品', '设计一个引起好奇心的开场', '用一个故事开头吸引观众'], tips: ['前5秒决定观众去留', '要有悬念或利益点', '声音要有感染力'] },
        product_intro: { desc: '练习有逻辑地介绍产品卖点', prompts: ['介绍这个产品的3个核心卖点', '用对比法突出产品优势', '讲述产品的产地故事'], tips: ['FAB法则：特点→优势→利益', '用具体数字说话', '配合实物展示'] },
        interaction: { desc: '练习与观众互动提升参与感', prompts: ['设计一个引导观众扣1的问题', '用选择题引导观众互动', '感谢观众并引导关注'], tips: ['每3分钟一次互动', '点名感谢活跃观众', '用问题引导下单'] },
        closing: { desc: '练习在关键时刻推动下单', prompts: ['用限时限量制造紧迫感', '用从众心理促单', '给出下单的理由和步骤'], tips: ['强调稀缺性', '降低决策门槛', '给出明确的下单指引'] },
        objection: { desc: '练习应对观众的质疑和异议', prompts: ['观众说太贵了怎么回应', '观众质疑品质怎么回答', '观众说要考虑一下怎么引导'], tips: ['先认同再引导', '用事实和数据说话', '不要和观众争论'] }
    };
    const s = scenarios[scenarioId] || scenarios.opening;
    const descEl = document.getElementById('scenario-desc');
    if (descEl) descEl.textContent = s.desc;
    const examplesEl = document.getElementById('prompt-examples');
    if (examplesEl) examplesEl.innerHTML = s.prompts.map(p => `<span class="prompt-tag">${p}</span>`).join('');
    const tipsEl = document.getElementById('practice-tips');
    if (tipsEl) tipsEl.querySelector('ul').innerHTML = s.tips.map(t => `<li>${t}</li>`).join('');
    // 隐藏之前的评分
    document.getElementById('practice-score')?.classList.add('is-hidden');
}

async function scorePractice() {
    const text = document.getElementById('practice-text')?.value?.trim();
    if (!text) { showNotification('请先输入直播话术', 'warning'); return; }
    showLoading('AI正在评分...');
    try {
        const data = await apiCall('/api/simulation/live-score', 'POST', {
            script: text,
            scenario: PracticeState.currentScenario
        });
        hideLoading();
        if (data.success && data.score) {
            renderPracticeScore(data.score);
        }
    } catch(e) {
        hideLoading();
        showNotification('评分服务暂时不可用', 'error');
    }
}

function renderPracticeScore(score) {
    const container = document.getElementById('score-metrics');
    if (!container) return;

    const metricLabels = {
        speed: '语速流畅', clarity: '逻辑清晰', engagement: '互动引导',
        product_knowledge: '产品知识', scenario_match: '场景匹配', overall: '综合得分'
    };
    const metricColors = {
        speed: '#3b82f6', clarity: '#8b5cf6', engagement: '#f59e0b',
        product_knowledge: '#22c55e', scenario_match: '#06b6d4', overall: '#ec4899'
    };

    const keys = Object.keys(metricLabels);
    container.innerHTML = keys.map(k => {
        const val = Math.round(score[k] || 0);
        const color = metricColors[k];
        return `<div class="score-metric-item">
            <div class="score-metric-label">${metricLabels[k]}</div>
            <div class="score-metric-bar"><div class="score-metric-fill" style="width:${val}%;background:${color}"></div></div>
            <div class="score-metric-value" style="color:${color}">${val}</div>
        </div>`;
    }).join('');

    // 反馈
    const feedbackEl = document.getElementById('score-feedback');
    if (feedbackEl) feedbackEl.textContent = score.feedback || '表现不错，继续练习！';

    // 亮点和改进
    const highlightsEl = document.getElementById('score-highlights');
    if (highlightsEl) {
        let html = '';
        if (score.highlights && score.highlights.length) {
            score.highlights.forEach(h => {
                const label = metricLabels[h] || h;
                html += `<span class="highlight-tag good">✓ ${label}</span>`;
            });
        }
        if (score.improvements && score.improvements.length) {
            score.improvements.forEach(h => {
                const label = metricLabels[h] || h;
                html += `<span class="highlight-tag improve">↑ 待提升：${label}</span>`;
            });
        }
        highlightsEl.innerHTML = html;
    }

    document.getElementById('practice-score')?.classList.remove('is-hidden');

    // 动画数字
    container.querySelectorAll('.score-metric-value').forEach(el => {
        const target = parseInt(el.textContent);
        animateNumber(el, target, 800);
    });
}

// ==================== 手工AR指导 ====================

const CraftARState = { currentCraft: 'embroidery', currentStep: 1, totalSteps: 5, initialized: false };

function initCraftAR() {
    if (CraftARState.initialized) return;
    CraftARState.initialized = true;

    // 手艺选择
    document.querySelectorAll('.craft-ar-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            document.querySelectorAll('.craft-ar-btn').forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            CraftARState.currentCraft = this.dataset.craft;
            CraftARState.currentStep = 1;
            loadCraftSteps();
            loadCraftGuide();
        });
    });

    loadCraftSteps();
    loadCraftGuide();
}

function loadCraftSteps() {
    const nav = document.getElementById('ar-steps-nav');
    if (!nav) return;
    // 从CRAFT_AR_GUIDES获取步数（默认5步）
    const stepCount = { embroidery: 5, woodcarving: 5, ceramics: 5 }[CraftARState.currentCraft] || 5;
    CraftARState.totalSteps = stepCount;
    nav.innerHTML = '';
    for (let i = 1; i <= stepCount; i++) {
        const btn = document.createElement('button');
        btn.className = 'ar-step-btn' + (i === CraftARState.currentStep ? ' active' : '');
        btn.textContent = i;
        btn.addEventListener('click', () => {
            CraftARState.currentStep = i;
            nav.querySelectorAll('.ar-step-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            loadCraftGuide();
        });
        nav.appendChild(btn);
    }
}

async function loadCraftGuide() {
    const canvas = document.getElementById('ar-canvas');
    const placeholder = canvas?.querySelector('.ar-placeholder');
    const stepDisplay = document.getElementById('ar-step-display');

    // 更新3D预览区
    if (placeholder) placeholder.classList.add('is-hidden');
    if (stepDisplay) {
        stepDisplay.classList.remove('is-hidden');
        document.getElementById('ar-step-number').textContent = CraftARState.currentStep;
    }

    try {
        const data = await apiCall('/api/simulation/craft-ar', 'POST', {
            craft: CraftARState.currentCraft,
            step: CraftARState.currentStep
        });
        if (data.success && data.guide) {
            renderCraftGuide(data.guide, data.total_steps);
        }
    } catch(e) {
        showNotification('加载指导失败', 'error');
    }
}

function renderCraftGuide(guide, totalSteps) {
    const stepTitle = document.getElementById('ar-step-title');
    if (stepTitle) stepTitle.textContent = guide.title || '';
    const desc = document.getElementById('guide-desc');
    if (desc) desc.textContent = guide.detailed_desc || guide.desc || '';
    const action = document.getElementById('guide-action');
    if (action) action.textContent = guide.action || '';
    const check = document.getElementById('guide-check');
    if (check) check.textContent = guide.check || '';
    const mistakes = document.getElementById('guide-mistakes');
    if (mistakes && guide.common_mistakes) {
        mistakes.innerHTML = guide.common_mistakes.map(m => `<li>${m}</li>`).join('');
    }
    const tips = document.getElementById('guide-tips');
    if (tips && guide.pro_tips) {
        tips.innerHTML = guide.pro_tips.map(t => `<li>${t}</li>`).join('');
    }
    const time = document.getElementById('guide-time');
    if (time) time.innerHTML = `<i class="fas fa-clock"></i> 预计耗时：${guide.estimated_time || '--'}`;
    const stepCount = document.getElementById('guide-step-count');
    if (stepCount) stepCount.innerHTML = `<i class="fas fa-list-ol"></i> 步骤 ${guide.step || CraftARState.currentStep}/${totalSteps || CraftARState.totalSteps}`;

    // 更新步骤按钮状态
    document.querySelectorAll('.ar-step-btn').forEach((btn, idx) => {
        if (idx < CraftARState.currentStep - 1) btn.classList.add('completed');
        else btn.classList.remove('completed');
    });
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
                // 更新产品标签
                const tag = document.getElementById('cam-product-tag');
                if (tag) tag.querySelector('span').textContent = getProductName(AppState.currentProduct);
                startLiveSimulation();
            } else if (module === 'product-copy') {
                openCopywritingPanel();
            } else if (module === 'store-design') {
                openStoreDesignPanel();
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
            navigator.clipboard.writeText(text).then(() => showNotification('话术已复制', 'success'));
        }
    });

    // 重新评分
    document.getElementById('re-score-btn')?.addEventListener('click', () => {
        const box = document.getElementById('live-script');
        const text = box?.innerText || '';
        if (text.trim() && !text.includes('选择话术风格')) {
            getLiveFeedback(text);
        }
    });

    // 话术风格切换
    document.querySelectorAll('.style-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            document.querySelectorAll('.style-btn').forEach(b => b.classList.remove('active'));
            this.classList.add('active');
        });
    });
}

// ==================== 直播模拟 ====================

const LiveState = {
    timer: null,
    seconds: 0,
    commentTimer: null,
    statTimer: null,
    viewers: 0,
    likes: 0,
    comments: 0,
    isRunning: false
};

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

function startLiveSimulation() {
    if (LiveState.isRunning) return;
    LiveState.isRunning = true;
    LiveState.seconds = 0;
    LiveState.viewers = Math.floor(Math.random() * 50) + 20;
    LiveState.likes = Math.floor(Math.random() * 100) + 50;
    LiveState.comments = 0;

    updateLiveStats();
    document.getElementById('live-badge')?.classList.add('active');

    // 计时器
    LiveState.timer = setInterval(() => {
        LiveState.seconds++;
        const mm = String(Math.floor(LiveState.seconds / 60)).padStart(2, '0');
        const ss = String(LiveState.seconds % 60).padStart(2, '0');
        const el = document.getElementById('live-duration');
        if (el) el.textContent = `${mm}:${ss}`;
    }, 1000);

    // 观众增长
    LiveState.statTimer = setInterval(() => {
        LiveState.viewers += Math.floor(Math.random() * 8) - 2;
        LiveState.viewers = Math.max(10, LiveState.viewers);
        LiveState.likes += Math.floor(Math.random() * 15);
        updateLiveStats();
    }, 3000);

    // 模拟评论
    const product = AppState.currentProduct || 'lychee';
    const comments = LIVE_COMMENTS[product] || LIVE_COMMENTS.lychee;
    const users = ['小明', '阿花', '老王', '靓妹', '农家大姐', '吃货小李', '广东阿叔', '深圳打工仔', '佛山靓女', '潮汕老板'];
    LiveState.commentTimer = setInterval(() => {
        const user = users[Math.floor(Math.random() * users.length)];
        const text = comments[Math.floor(Math.random() * comments.length)];
        addLiveComment(user, text);
        LiveState.comments++;
        const el = document.getElementById('comment-count');
        if (el) el.textContent = LiveState.comments;
    }, 2500 + Math.random() * 3000);
}

function stopLiveSimulation() {
    LiveState.isRunning = false;
    clearInterval(LiveState.timer);
    clearInterval(LiveState.statTimer);
    clearInterval(LiveState.commentTimer);
    document.getElementById('live-badge')?.classList.remove('active');
}

function updateLiveStats() {
    const ve = document.getElementById('viewer-count');
    const le = document.getElementById('like-count');
    if (ve) ve.textContent = LiveState.viewers;
    if (le) le.textContent = LiveState.likes;
}

function addLiveComment(user, text) {
    const container = document.getElementById('live-comments');
    if (!container) return;
    const div = document.createElement('div');
    div.className = 'comment-item comment-new';
    div.innerHTML = `<span class="comment-user">${user}：</span>${text}`;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
    // 限制评论数量
    while (container.children.length > 30) container.firstChild.remove();
}

async function generateLiveScript() {
    const scriptContent = document.getElementById('live-script');
    const style = document.querySelector('.style-btn.active')?.dataset.style || '热情';
    const product = AppState.currentProduct || 'lychee';
    const productName = getProductName(product);

    // 更新产品标签
    const tag = document.getElementById('cam-product-tag');
    if (tag) tag.querySelector('span').textContent = productName;

    showSkeleton(scriptContent, 'text', 5);
    startLiveSimulation();

    try {
        const data = await apiCall('/api/ecommerce/script', 'POST', { product: productName, style });
        if (data.success) {
            scriptContent.innerHTML = '<p style="white-space:pre-line;" id="script-typewriter"></p>';
            const tw = document.getElementById('script-typewriter');
            await typewriterEffect(tw, data.script);
            showNotification(`${style}风格话术已生成！`, 'success');
            getLiveFeedback(data.script);
        }
    } catch(e) {
        const fallbackScripts = {
            '热情': `家人们！今天给你们带来广东最正宗的${productName}！\n(互动) 想要的扣1，让我看看有多少人识货！\n你们看这个品相，【颗颗饱满】，色泽鲜亮，这可不是随便哪里都能找到的！\n原价128，今天直播间专属价——只要【79元】！没听错，79！\n(引导) 觉得值的给我点个赞，点到500我再送一份赠品！\n最后30单，拍完就恢复原价，手慢无！`,
            '专业': `各位朋友好，今天给大家带来的是广东${productName}。\n这个品种产自岭南核心产区，年均气温22°C，日照充足，土壤富含矿物质。\n我们每一批都经过【农残检测、甜度筛选】，检测报告大家可以看屏幕。\n和市面上的普通产品相比，我们的优势在于：果径大15%、甜度高3度、保鲜期多5天。\n今天直播间特惠，【买二送一】，性价比非常高的。`,
            '故事': `在广东的一个小村子里，有位老师傅种了30年${productName}。\n他常说："好东西急不得，要等天时、靠地利、更要用心。"\n(停顿) 每年这个时候，他凌晨4点就下地，只为赶在日出前采摘最新鲜的一批。\n从枝头到你手里，不超过48小时——这就是我们对品质的承诺。\n今天把这份来自岭南的匠心之味带给大家，【尝过的都说好】。\n(引导) 想尝尝这份用心的，点下方链接下单吧。`,
            '高级': `岭南夏日，最令人期待的，莫过于这口来自广东的${productName}。\n它生长在北回归线以南的沃土，吸饱了亚热带的阳光和雨露。\n【果肉如玉，汁水丰盈】，入口即化的细腻口感，是大自然最好的馈赠。\n古人云"日啖荔枝三百颗"，而今这份岭南风物，只需一键下单便可抵达你的餐桌。\n今日限量供应，【精品礼盒装】，自用送礼皆宜。\n品味不将就，生活要讲究。`
        };
        scriptContent.innerHTML = `<p style="white-space:pre-line;">${fallbackScripts[style] || fallbackScripts['热情']}</p>`;
        getLiveFeedback(fallbackScripts[style] || fallbackScripts['热情']);
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
    if (score >= 90) return { text: 'S', color: '#10b981', label: '优秀' };
    if (score >= 80) return { text: 'A', color: '#22c55e', label: '良好' };
    if (score >= 70) return { text: 'B', color: '#f59e0b', label: '中等' };
    if (score >= 60) return { text: 'C', color: '#f97316', label: '及格' };
    return { text: 'D', color: '#ef4444', label: '需改进' };
}

function getScoreColor(score) {
    if (score >= 85) return '#10b981';
    if (score >= 70) return '#22c55e';
    if (score >= 55) return '#f59e0b';
    return '#ef4444';
}

function renderFeedbackMetrics(metrics) {
    const container = document.getElementById('feedback-metrics');
    if (!container) return;
    container.innerHTML = '';
    const keys = Object.keys(METRIC_LABELS);
    keys.forEach((key, i) => {
        const score = metrics[key] || 0;
        const config = METRIC_LABELS[key];
        const color = getScoreColor(score);
        const div = document.createElement('div');
        div.className = 'metric';
        div.innerHTML = `
            <label><i class="fas ${config.icon}"></i> ${config.label}</label>
            <div class="progress-bar"><div class="progress-fill" id="fb-${key}" style="width:0%"></div></div>
            <span id="fb-${key}-val" style="color:${color}">-</span>
        `;
        container.appendChild(div);
        // 延迟动画
        setTimeout(() => animateScore(`fb-${key}`, `fb-${key}-val`, score), i * 150);
    });
}

// 基于话术内容分析生成差异化分数
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

    const jitter = () => Math.floor(Math.random() * 7) - 3;
    speed = Math.min(98, Math.max(50, speed + jitter()));
    emotion = Math.min(98, Math.max(50, emotion + jitter()));
    interaction = Math.min(98, Math.max(50, interaction + jitter()));
    selling = Math.min(98, Math.max(50, selling + jitter()));

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
        suggestions.push('用具体数据支撑卖点，如甜度、重量、检测指标');
    }
    if (scores.emotion_score < 72 && !hasEmotion) {
        suggestions.push('增加情绪词和感叹句，如"这也太香了吧！"');
    }
    if (!hasPrice) {
        suggestions.push('加入价格锚点，如"原价128，今天只要79"');
    }
    if (scores.selling_score >= 75 && scores.interaction_score >= 75) {
        suggestions.push('整体不错，可以尝试讲故事增加情感共鸣');
    }

    const general = [
        '开场3秒内抛出核心卖点抓住注意力',
        '用"最后XX单"制造紧迫感促进下单',
        '加入用户好评或复购数据增强信任',
        '结尾引导关注直播间获取更多优惠',
        '用对比法突出产品差异化优势'
    ];
    general.sort(() => Math.random() - 0.5);
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

    if (placeholder) placeholder.classList.add('is-hidden');
    if (body) body.classList.remove('is-hidden');
    if (reScoreBtn) reScoreBtn.classList.remove('is-hidden');

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
        }
    } catch(e) {
        // 基于话术内容分析生成差异化分数
        const analyzed = analyzeScript(script);
        renderFeedbackMetrics(analyzed);

        const overall = Math.round(Object.values(analyzed).reduce((a, b) => a + b, 0) / 4);
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
    }
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

function animateNumber(el, target, duration = 1000) {
    let start = 0;
    const startTime = performance.now();
    function update(now) {
        const elapsed = now - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3);
        el.textContent = Math.round(start + (target - start) * eased);
        if (progress < 1) requestAnimationFrame(update);
    }
    requestAnimationFrame(update);
}

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
            <div class="copy-config">
                <div class="copy-config-row">
                    <div class="form-group">
                        <label><i class="fas fa-box"></i> 产品名称</label>
                        <input type="text" id="copy-product" placeholder="例如：增城桂味荔枝" value="${preset.name}">
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
        </div>
    `);

    // 格式切换
    const formatDescs = {
        '详情页': '电商商品详情页文案，层次分明，卖点突出',
        '主图文案': '5条独立主图文案，每条8-15字，简洁有力',
        '朋友圈': '微信朋友圈推广文案，真实自然，像朋友分享',
        '小红书': '小红书种草笔记，种草感强，闺蜜推荐风格',
        '短视频脚本': '15-30秒短视频带货脚本，按时间轴输出'
    };
    let currentFormat = '详情页';

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

    async function generate() {
        const product = document.getElementById('copy-product').value.trim();
        if (!product) { showNotification('请输入产品名称', 'warning'); return; }

        const audience = document.getElementById('copy-audience').value;
        const selling_points = document.getElementById('copy-points').value.trim();

        showSkeleton(resultDiv, 'text', 5);
        generateBtn.disabled = true;
        generateBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 生成中...';

        try {
            const data = await apiCall('/api/ecommerce/copywriting', 'POST', {
                product, format: currentFormat, audience, selling_points
            });
            if (data.success) {
                resultDiv.innerHTML = `
                    <div class="copy-result">
                        <div class="copy-result-header">
                            <span class="copy-result-tag"><i class="fas fa-file-alt"></i> ${currentFormat}</span>
                            <div class="copy-result-actions">
                                <button class="btn btn-outline btn-sm" id="copy-result-btn"><i class="fas fa-copy"></i> 复制</button>
                            </div>
                        </div>
                        <div class="copy-result-body" id="copy-result-body"></div>
                    </div>
                `;
                const body = document.getElementById('copy-result-body');
                await typewriterEffect(body, data.copywriting);
                body.innerHTML = formatAnswer(data.copywriting);

                document.getElementById('copy-result-btn')?.addEventListener('click', () => {
                    navigator.clipboard.writeText(data.copywriting).then(() => showNotification('文案已复制', 'success'));
                });

                regenBtn.style.display = 'inline-flex';
            }
        } catch(e) {
            showErrorState(resultDiv, '生成失败，请重试', generate);
        } finally {
            generateBtn.disabled = false;
            generateBtn.innerHTML = '<i class="fas fa-magic"></i> AI生成文案';
        }
    }

    generateBtn?.addEventListener('click', generate);
    regenBtn?.addEventListener('click', generate);
}

function openStoreDesignPanel() {
    const productName = getProductName(AppState.currentProduct);
    showDetailModal('店铺装修指导', `
        <div class="store-design-panel">
            <div class="store-config">
                <div class="store-config-row">
                    <div class="form-group">
                        <label><i class="fas fa-store"></i> 店铺类型</label>
                        <select id="store-type">
                            <option value="农产品店铺">农产品店铺</option>
                            <option value="水果生鲜店铺">水果生鲜店铺</option>
                            <option value="茶叶店铺">茶叶店铺</option>
                            <option value="手工艺品店铺">手工艺品店铺</option>
                            <option value="地方特产店铺">地方特产店铺</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label><i class="fas fa-shopping-cart"></i> 电商平台</label>
                        <select id="store-platform">
                            <option value="淘宝">淘宝</option>
                            <option value="拼多多">拼多多</option>
                            <option value="抖音小店">抖音小店</option>
                            <option value="微信小程序">微信小程序</option>
                            <option value="京东">京东</option>
                        </select>
                    </div>
                </div>
                <div class="store-config-row">
                    <div class="form-group">
                        <label><i class="fas fa-palette"></i> 视觉风格</label>
                        <select id="store-style">
                            <option value="清新自然">清新自然</option>
                            <option value="高端大气">高端大气</option>
                            <option value="年轻活泼">年轻活泼</option>
                            <option value="传统国风">传统国风</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label><i class="fas fa-box"></i> 主营产品</label>
                        <input type="text" id="store-product" value="${productName}" placeholder="例如：荔枝、龙眼">
                    </div>
                </div>
            </div>

            <div class="store-modules">
                <label class="form-label"><i class="fas fa-th-large"></i> 选择指导模块</label>
                <div class="module-cards" id="store-module-cards">
                    <button class="module-card-btn active" data-module="首页布局">
                        <i class="fas fa-home"></i>
                        <span>首页布局</span>
                        <small>整体页面规划</small>
                    </button>
                    <button class="module-card-btn" data-module="色彩方案">
                        <i class="fas fa-palette"></i>
                        <span>色彩方案</span>
                        <small>配色与色值</small>
                    </button>
                    <button class="module-card-btn" data-module="详情页设计">
                        <i class="fas fa-file-alt"></i>
                        <span>详情页</span>
                        <small>商品详情结构</small>
                    </button>
                    <button class="module-card-btn" data-module="主图设计">
                        <i class="fas fa-image"></i>
                        <span>主图设计</span>
                        <small>5张主图策略</small>
                    </button>
                    <button class="module-card-btn" data-module="分类导航">
                        <i class="fas fa-bars"></i>
                        <span>分类导航</span>
                        <small>导航逻辑设计</small>
                    </button>
                </div>
            </div>

            <div class="form-group">
                <label><i class="fas fa-comment-dots"></i> 补充需求 <span class="hint">（选填）</span></label>
                <textarea id="store-needs" rows="2" placeholder="描述你的具体需求，如：希望突出岭南特色、适合送礼场景..."></textarea>
            </div>

            <div class="copy-actions">
                <button class="btn btn-primary" id="get-store-design-btn">
                    <i class="fas fa-magic"></i> 生成装修指导
                </button>
                <button class="btn btn-outline btn-sm" id="regenerate-store-btn" style="display:none;">
                    <i class="fas fa-redo"></i> 换一版
                </button>
            </div>

            <div id="store-design-result"></div>
        </div>
    `);

    let currentModule = '首页布局';

    // 模块切换
    document.querySelectorAll('.module-card-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            document.querySelectorAll('.module-card-btn').forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            currentModule = this.dataset.module;
        });
    });

    // 生成指导
    const generateBtn = document.getElementById('get-store-design-btn');
    const regenBtn = document.getElementById('regenerate-store-btn');
    const resultDiv = document.getElementById('store-design-result');

    async function generate() {
        const store_type = document.getElementById('store-type').value;
        const platform = document.getElementById('store-platform').value;
        const style = document.getElementById('store-style').value;
        const product = document.getElementById('store-product').value.trim();
        const needs = document.getElementById('store-needs').value.trim();

        showSkeleton(resultDiv, 'text', 5);
        generateBtn.disabled = true;
        generateBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 生成中...';

        try {
            const data = await apiCall('/api/ecommerce/store-design', 'POST', {
                store_type, platform, style, module: currentModule, product, needs
            });
            if (data.success) {
                resultDiv.innerHTML = `
                    <div class="copy-result">
                        <div class="copy-result-header">
                            <span class="copy-result-tag"><i class="fas fa-paint-brush"></i> ${currentModule}</span>
                            <div class="copy-result-actions">
                                <button class="btn btn-outline btn-sm" id="store-result-btn"><i class="fas fa-copy"></i> 复制</button>
                            </div>
                        </div>
                        <div class="copy-result-body" id="store-result-body"></div>
                    </div>
                `;
                const body = document.getElementById('store-result-body');
                await typewriterEffect(body, data.design);
                body.innerHTML = formatAnswer(data.design);

                document.getElementById('store-result-btn')?.addEventListener('click', () => {
                    navigator.clipboard.writeText(data.design).then(() => showNotification('指导内容已复制', 'success'));
                });

                regenBtn.style.display = 'inline-flex';
            }
        } catch(e) {
            showErrorState(resultDiv, '生成失败，请重试', generate);
        } finally {
            generateBtn.disabled = false;
            generateBtn.innerHTML = '<i class="fas fa-magic"></i> 生成装修指导';
        }
    }

    generateBtn?.addEventListener('click', generate);
    regenBtn?.addEventListener('click', generate);
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
                        </div>
                    </div>
                    <div class="cs-input-bar">
                        <input type="text" id="cs-input" placeholder="作为客服回复客户..." disabled>
                        <button class="btn btn-primary" id="cs-send-btn" disabled><i class="fas fa-paper-plane"></i></button>
                    </div>
                </div>
                <div class="cs-sidebar">
                    <div class="cs-score-card" id="cs-score-card">
                        <h4><i class="fas fa-chart-radar"></i> 实时评分</h4>
                        <div class="cs-score-overall" id="cs-score-overall">-</div>
                        <div class="cs-score-label">综合得分</div>
                        <div class="cs-score-bars" id="cs-score-bars">
                            <div class="cs-score-bar">
                                <span>礼貌度</span>
                                <div class="progress-bar"><div class="progress-fill" id="cs-polite" style="width:0%"></div></div>
                                <em id="cs-polite-val">-</em>
                            </div>
                            <div class="cs-score-bar">
                                <span>专业度</span>
                                <div class="progress-bar"><div class="progress-fill" id="cs-pro" style="width:0%"></div></div>
                                <em id="cs-pro-val">-</em>
                            </div>
                            <div class="cs-score-bar">
                                <span>解决力</span>
                                <div class="progress-bar"><div class="progress-fill" id="cs-solve" style="width:0%"></div></div>
                                <em id="cs-solve-val">-</em>
                            </div>
                            <div class="cs-score-bar">
                                <span>同理心</span>
                                <div class="progress-bar"><div class="progress-fill" id="cs-empathy" style="width:0%"></div></div>
                                <em id="cs-empathy-val">-</em>
                            </div>
                        </div>
                    </div>
                    <div class="cs-tips-card" id="cs-tips-card">
                        <h4><i class="fas fa-lightbulb"></i> 实时建议</h4>
                        <div class="cs-tips-list" id="cs-tips-list">
                            <div class="cs-tip-item">开始对话后将显示建议</div>
                        </div>
                    </div>
                    <div class="cs-history-card">
                        <h4><i class="fas fa-history"></i> 对话轮次</h4>
                        <div class="cs-round-count" id="cs-round-count">0 轮</div>
                    </div>
                </div>
            </div>
        </div>
    `);

    const chatHistory = [];
    let isStarted = false;

    const startBtn = document.getElementById('cs-start-btn');
    const resetBtn = document.getElementById('cs-reset-btn');
    const hintBtn = document.getElementById('cs-hint-btn');
    const sendBtn = document.getElementById('cs-send-btn');
    const chatInput = document.getElementById('cs-input');
    const messagesDiv = document.getElementById('cs-messages');

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
                chatInput.focus();
            }
        } catch(e) {
            appendCSMsg('customer', '你好，我想问一下...');
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

        appendCSMsg('agent', msg);

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

                // 更新评分
                if (data.score && data.score.total > 0) {
                    updateCSScore(data.score);
                }

                // 更新轮次
                const rounds = Math.floor(chatHistory.length / 2);
                document.getElementById('cs-round-count').textContent = `${rounds} 轮`;
            }
        } catch(e) {
            typingDiv.remove();
            chatHistory.push({ role: 'user', content: msg });
            chatHistory.push({ role: 'assistant', content: '嗯...我想想...' });
            appendCSMsg('customer', '嗯...我想想...');
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
            </div>
        `;
        chatHistory.length = 0;
        isStarted = false;
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
        document.getElementById('cs-tips-list').innerHTML = '<div class="cs-tip-item">开始对话后将显示建议</div>';
        document.getElementById('cs-round-count').textContent = '0 轮';
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
                // 点击复制话术
                tipsList.querySelectorAll('.cs-hint-tpl').forEach(el => {
                    el.addEventListener('click', () => {
                        navigator.clipboard.writeText(el.dataset.text).then(() => {
                            showNotification('已复制到剪贴板', 'success');
                            el.classList.add('copied');
                            setTimeout(() => el.classList.remove('copied'), 1500);
                        });
                    });
                });
            }
        } catch(e) {
            if (tipsList) {
                tipsList.innerHTML = '<div class="cs-tip-item"><i class="fas fa-exclamation-circle"></i> 获取建议失败，请重试</div>';
            }
        }
    });
}

function appendCSMsg(role, text) {
    const container = document.getElementById('cs-messages');
    if (!container) return;
    // 移除欢迎信息
    container.querySelector('.cs-welcome')?.remove();

    const div = document.createElement('div');
    div.className = `cs-msg ${role}`;
    const icon = role === 'customer' ? 'fa-user' : 'fa-headset';
    const label = role === 'customer' ? '客户' : '你（客服）';
    div.innerHTML = `
        <div class="cs-msg-avatar"><i class="fas ${icon}"></i></div>
        <div class="cs-msg-content">
            <div class="cs-msg-label">${label}</div>
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
        const color = score.total >= 85 ? '#10b981' : score.total >= 70 ? '#22c55e' : score.total >= 55 ? '#f59e0b' : '#ef4444';
        totalEl.style.color = color;
    }

    if (score.details) {
        const mapping = [
            { key: 'politeness', fill: 'cs-polite', val: 'cs-polite-val' },
            { key: 'professional', fill: 'cs-pro', val: 'cs-pro-val' },
            { key: 'solving', fill: 'cs-solve', val: 'cs-solve-val' },
            { key: 'empathy', fill: 'cs-empathy', val: 'cs-empathy-val' }
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

function setupPolicySection() {
    // 分类筛选
    document.querySelectorAll('.policy-filter').forEach(btn => {
        btn.addEventListener('click', function() {
            document.querySelectorAll('.policy-filter').forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            const filter = this.dataset.filter;
            document.querySelectorAll('.policy-card').forEach(card => {
                if (filter === 'all' || card.dataset.category === filter) {
                    card.style.display = '';
                } else {
                    card.style.display = 'none';
                }
            });
        });
    });

    // 政策卡片点击 → 弹窗
    document.querySelectorAll('.policy-card').forEach(card => {
        card.addEventListener('click', async function() {
            const title = this.querySelector('h4')?.textContent || '';
            showLoading('加载政策详情...');
            try {
                const data = await apiCall('/api/resources/policies');
                hideLoading();
                if (data.success && data.policies) {
                    const policy = data.policies.find(p => p.title === title);
                    if (policy) {
                        showPolicyModal(policy);
                        return;
                    }
                }
                showNotification('未找到该政策详情', 'warning');
            } catch(e) {
                hideLoading();
                showNotification('加载失败，请稍后重试', 'error');
            }
        });
    });
}

function showPolicyModal(policy) {
    // 解析内容为HTML
    const html = formatPolicyContent(policy.content);
    showDetailModal(policy.title, `<div class="policy-detail-content">${html}</div>`);
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
            html += `<h4>${trimmed.slice(1, -1)}</h4>`;
            continue;
        }

        // 无序列表：• 开头
        if (trimmed.startsWith('•') || trimmed.startsWith('-')) {
            if (!inList) { html += '<ul>'; inList = true; listType = 'ul'; }
            html += `<li>${trimmed.slice(1).trim()}</li>`;
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
            html += `<li>${trimmed.replace(/^\d+\.\s*/, '')}</li>`;
            continue;
        }

        // 普通段落
        if (inList) { html += `</${listType}>`; inList = false; }
        html += `<p>${trimmed}</p>`;
    }

    if (inList) html += `</${listType}>`;
    return html;
}

// ==================== 就业模块 ====================

function setupEmploymentTab() {
    setupEmploymentSubTabs();
    setupEmploymentSearch();
    setupApplicationStatusTabs();
    setupStartupSupportLinks();
    setupPointsExchange();
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
            if (target === 'applications') loadUserApplications();
            if (target === 'saved') loadSavedJobs();
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
            loadUserApplications(tab.dataset.status);
        });
    });
}

const STARTUP_SERVICES = [
    {
        id: 'project',
        icon: 'fas fa-file-alt',
        title: '项目申报指导',
        subtitle: '专业团队全程辅导',
        desc: '提供专业的农业项目申报指导服务，覆盖国家及省级各类农业扶持项目。由资深政策分析师一对一辅导，从项目筛选、方案设计到材料准备、提交跟踪，全程陪伴助力成功申报。',
        steps: [
            { name: '需求咨询', desc: '了解您的创业方向和资源条件' },
            { name: '项目评估', desc: '匹配适合的政策扶持项目' },
            { name: '材料准备', desc: '协助编写商业计划书及申报材料' },
            { name: '提交申报', desc: '对接主管部门提交申请' },
            { name: '跟踪反馈', desc: '持续跟进审批进度直至落地' }
        ],
        projects: ['农业产业化项目', '乡村振兴示范项目', '农业科技攻关项目', '农产品加工补贴项目', '农村一二三产业融合项目'],
        stats: { successRate: '87%', avgDays: '30天', totalHelped: '260+' },
        hotline: '0668-2888-xxx'
    },
    {
        id: 'funding',
        icon: 'fas fa-money-bill-wave',
        title: '资金申请协助',
        subtitle: '对接多种低息贷款渠道',
        desc: '帮助创业者对接银行、信用社、担保公司等多种资金渠道，提供贷款方案咨询、材料准备、利率谈判等服务，解决创业资金难题。与多家金融机构建立合作关系，享受专属优惠利率。',
        channels: [
            { name: '农业银行惠农贷款', rate: '年利率3.85%起', limit: '最高50万', period: '1-3年' },
            { name: '农村信用社小额贷款', rate: '年利率4.35%起', limit: '最高20万', period: '1-5年' },
            { name: '创业担保贷款', rate: '政府贴息', limit: '最高30万', period: '2-3年' },
            { name: '农业保险补贴', rate: '保费补贴80%', limit: '按种植面积', period: '1年' }
        ],
        requirements: ['年满18周岁，具有完全民事行为能力', '有明确的创业项目和可行的商业计划', '信用记录良好，无重大不良信用', '有固定的经营场所或种植基地'],
        hotline: '0668-2888-xxx'
    },
    {
        id: 'market',
        icon: 'fas fa-store',
        title: '市场渠道对接',
        subtitle: '线上线下全渠道覆盖',
        desc: '提供全方位的市场渠道对接服务，帮助农产品走出乡村、走向全国。整合线上线下资源，对接电商平台、批发市场、商超、社区团购等多种销售渠道，让好产品卖出好价钱。',
        channels: [
            { name: '电商平台', items: ['淘宝/天猫', '拼多多', '抖音电商', '京东生鲜'], icon: 'fas fa-globe' },
            { name: '线下批发', items: ['广州江南市场', '深圳海吉星', '佛山中南市场'], icon: 'fas fa-warehouse' },
            { name: '社区团购', items: ['美团优选', '多多买菜', '兴盛优选'], icon: 'fas fa-users' },
            { name: '直播带货', items: ['抖音直播', '快手直播', '视频号直播'], icon: 'fas fa-video' }
        ],
        successCases: [
            { name: '高州荔枝', result: '通过抖音直播单日销售5000斤' },
            { name: '化州橘红', result: '入驻天猫旗舰店月销20万+' },
            { name: '信宜三华李', result: '社区团购覆盖珠三角300+社区' }
        ],
        hotline: '0668-2888-xxx'
    }
];

function setupStartupSupportLinks() {
    document.querySelectorAll('.emp-startup-item').forEach(item => {
        item.addEventListener('click', () => {
            const idx = parseInt(item.dataset.support);
            openStartupDetail(idx);
        });
    });
    const viewAll = document.getElementById('emp-startup-view-all');
    if (viewAll) viewAll.addEventListener('click', openStartupOverview);
}

function openStartupOverview() {
    const cards = STARTUP_SERVICES.map((s, i) => `
        <div class="startup-overview-card" data-idx="${i}">
            <div class="startup-overview-icon"><i class="${s.icon}"></i></div>
            <div class="startup-overview-info">
                <div class="startup-overview-title">${s.title}</div>
                <div class="startup-overview-subtitle">${s.subtitle}</div>
            </div>
            <i class="fas fa-arrow-right startup-overview-arrow"></i>
        </div>
    `).join('');
    const html = `
        <div class="startup-overview-scroll">
            <div class="startup-overview-intro">
                <i class="fas fa-info-circle"></i>
                <span>粤乡智匠为创业者提供从项目申报、资金对接到市场渠道的全链条创业支持服务</span>
            </div>
            <div class="startup-overview-list">${cards}</div>
            <div class="startup-overview-contact">
                <i class="fas fa-headset"></i>
                <span>创业热线：<strong>0668-2888-xxx</strong>（工作日 9:00-18:00）</span>
            </div>
        </div>
    `;
    showDetailModal('创业支持服务', html);
    document.querySelectorAll('.startup-overview-card').forEach(card => {
        card.addEventListener('click', () => {
            document.querySelector('.modal-overlay')?.click();
            setTimeout(() => openStartupDetail(parseInt(card.dataset.idx)), 200);
        });
    });
}

function openStartupDetail(idx) {
    const s = STARTUP_SERVICES[idx];
    if (!s) return;
    let body = '';

    if (s.id === 'project') {
        body = `
            <div class="startup-detail-scroll">
                <div class="startup-detail-hero">
                    <div class="startup-detail-hero-icon"><i class="${s.icon}"></i></div>
                    <div class="startup-detail-hero-info">
                        <div class="startup-detail-hero-title">${s.title}</div>
                        <div class="startup-detail-hero-subtitle">${s.subtitle}</div>
                    </div>
                </div>
                <div class="startup-detail-stats">
                    <div class="startup-detail-stat">
                        <span class="startup-detail-stat-num">${s.stats.successRate}</span>
                        <span class="startup-detail-stat-label">申报成功率</span>
                    </div>
                    <div class="startup-detail-stat">
                        <span class="startup-detail-stat-num">${s.stats.avgDays}</span>
                        <span class="startup-detail-stat-label">平均周期</span>
                    </div>
                    <div class="startup-detail-stat">
                        <span class="startup-detail-stat-num">${s.stats.totalHelped}</span>
                        <span class="startup-detail-stat-label">已服务客户</span>
                    </div>
                </div>
                <div class="startup-detail-desc">${s.desc}</div>
                <div class="startup-detail-subsection">
                    <div class="startup-detail-subtitle"><i class="fas fa-route"></i> 服务流程</div>
                    <div class="startup-detail-steps">
                        ${s.steps.map((st, i) => `
                            <div class="startup-detail-step">
                                <div class="startup-detail-step-num">${i + 1}</div>
                                <div class="startup-detail-step-content">
                                    <div class="startup-detail-step-name">${st.name}</div>
                                    <div class="startup-detail-step-desc">${st.desc}</div>
                                </div>
                            </div>
                        `).join('')}
                    </div>
                </div>
                <div class="startup-detail-subsection">
                    <div class="startup-detail-subtitle"><i class="fas fa-list-check"></i> 可申报项目</div>
                    <div class="startup-detail-tags">
                        ${s.projects.map(p => `<span class="startup-detail-tag">${p}</span>`).join('')}
                    </div>
                </div>
                <div class="startup-detail-contact">
                    <i class="fas fa-phone-volume"></i>
                    <span>咨询热线：<strong>${s.hotline}</strong></span>
                </div>
            </div>
        `;
    } else if (s.id === 'funding') {
        body = `
            <div class="startup-detail-scroll">
                <div class="startup-detail-hero">
                    <div class="startup-detail-hero-icon"><i class="${s.icon}"></i></div>
                    <div class="startup-detail-hero-info">
                        <div class="startup-detail-hero-title">${s.title}</div>
                        <div class="startup-detail-hero-subtitle">${s.subtitle}</div>
                    </div>
                </div>
                <div class="startup-detail-desc">${s.desc}</div>
                <div class="startup-detail-subsection">
                    <div class="startup-detail-subtitle"><i class="fas fa-university"></i> 资金渠道</div>
                    <div class="startup-funding-grid">
                        ${s.channels.map(ch => `
                            <div class="startup-funding-card">
                                <div class="startup-funding-name">${ch.name}</div>
                                <div class="startup-funding-detail">
                                    <span><i class="fas fa-percentage"></i> ${ch.rate}</span>
                                    <span><i class="fas fa-coins"></i> ${ch.limit}</span>
                                    <span><i class="fas fa-clock"></i> ${ch.period}</span>
                                </div>
                            </div>
                        `).join('')}
                    </div>
                </div>
                <div class="startup-detail-subsection">
                    <div class="startup-detail-subtitle"><i class="fas fa-clipboard-check"></i> 申请条件</div>
                    <div class="startup-detail-checklist">
                        ${s.requirements.map(r => `<div class="startup-detail-check"><i class="fas fa-check-circle"></i>${r}</div>`).join('')}
                    </div>
                </div>
                <div class="startup-detail-contact">
                    <i class="fas fa-phone-volume"></i>
                    <span>咨询热线：<strong>${s.hotline}</strong></span>
                </div>
            </div>
        `;
    } else if (s.id === 'market') {
        body = `
            <div class="startup-detail-scroll">
                <div class="startup-detail-hero">
                    <div class="startup-detail-hero-icon"><i class="${s.icon}"></i></div>
                    <div class="startup-detail-hero-info">
                        <div class="startup-detail-hero-title">${s.title}</div>
                        <div class="startup-detail-hero-subtitle">${s.subtitle}</div>
                    </div>
                </div>
                <div class="startup-detail-desc">${s.desc}</div>
                <div class="startup-detail-subsection">
                    <div class="startup-detail-subtitle"><i class="fas fa-th-large"></i> 销售渠道</div>
                    <div class="startup-market-grid">
                        ${s.channels.map(ch => `
                            <div class="startup-market-card">
                                <div class="startup-market-card-header">
                                    <i class="${ch.icon}"></i>
                                    <span>${ch.name}</span>
                                </div>
                                <div class="startup-market-items">
                                    ${ch.items.map(it => `<span class="startup-market-item">${it}</span>`).join('')}
                                </div>
                            </div>
                        `).join('')}
                    </div>
                </div>
                <div class="startup-detail-subsection">
                    <div class="startup-detail-subtitle"><i class="fas fa-trophy"></i> 成功案例</div>
                    <div class="startup-detail-cases">
                        ${s.successCases.map(c => `
                            <div class="startup-detail-case">
                                <div class="startup-detail-case-name">${c.name}</div>
                                <div class="startup-detail-case-result">${c.result}</div>
                            </div>
                        `).join('')}
                    </div>
                </div>
                <div class="startup-detail-contact">
                    <i class="fas fa-phone-volume"></i>
                    <span>咨询热线：<strong>${s.hotline}</strong></span>
                </div>
            </div>
        `;
    }
    showDetailModal(s.title, body);
}

async function loadEmploymentData() {
    // 职位列表不需要登录即可加载
    await loadJobListings();
    if (!AppState.user) return;
    await Promise.all([
        loadEmploymentStats(),
        loadCertificateSummary()
    ]);
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
            if (data.jobs.length === 0) {
                listEl.innerHTML = '';
                if (emptyEl) emptyEl.style.display = 'block';
            } else {
                if (emptyEl) emptyEl.style.display = 'none';
                // 获取收藏状态
                let savedIds = [];
                if (AppState.user) {
                    try {
                        const savedData = await apiCall(`/api/employment/saved/${AppState.user.id}`);
                        if (savedData.success) savedIds = savedData.saved_ids;
                    } catch(e) {}
                }
                listEl.innerHTML = data.jobs.map(job => renderJobCard(job, savedIds)).join('');
                bindJobCardEvents(listEl);
            }
            if (totalEl) totalEl.textContent = data.jobs.length;
        }
    } catch(e) {
        showErrorState(listEl, '加载职位失败', () => loadJobListings(filters));
    }
}

function renderJobCard(job, savedIds = []) {
    const initial = getCompanyInitial(job.company);
    const dateStr = computeRelativeDate(job.posted_at);
    const isSaved = savedIds.includes(job.id);
    const tags = (job.requirements || []).slice(0, 3);
    if (job.category) tags.unshift(job.category);

    return `
    <div class="emp-job-card" data-job-id="${job.id}">
        <div class="emp-job-card-left">
            <div class="emp-company-logo">${initial}</div>
        </div>
        <div class="emp-job-card-body">
            <div class="emp-job-header">
                <span class="emp-job-title">${job.title}</span>
                <span class="emp-job-salary">${job.salary}</span>
            </div>
            <div class="emp-job-company">
                ${job.company}<span class="emp-dot">·</span>${job.location || '广东'}<span class="emp-dot">·</span>${job.experience || '不限'}<span class="emp-dot">·</span>${job.education || '不限'}
            </div>
            <div class="emp-job-tags">
                ${tags.map(t => `<span class="emp-tag">${t}</span>`).join('')}
            </div>
        </div>
        <div class="emp-job-card-right">
            <span class="emp-job-date">${dateStr}</span>
            <button class="btn btn-primary btn-sm emp-apply-btn" data-job-id="${job.id}">申请职位</button>
            <button class="emp-save-btn ${isSaved ? 'saved' : ''}" data-job-id="${job.id}" title="${isSaved ? '取消收藏' : '收藏'}">
                <i class="${isSaved ? 'fas' : 'far'} fa-heart"></i>
            </button>
        </div>
    </div>`;
}

function bindJobCardEvents(container) {
    // 卡片点击 → 详情
    container.querySelectorAll('.emp-job-card').forEach(card => {
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
                <h4><i class="fas fa-star" style="color:#f59e0b;margin-right:6px;"></i>职位亮点</h4>
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
                <h4><i class="fas fa-lightbulb" style="color:#f59e0b;margin-right:6px;"></i>申请建议</h4>
                <div class="emp-detail-tips">
                    <p>1. 确保简历中突出了与该岗位相关的技能和经验</p>
                    <p>2. 如持有相关证书，请在简历中标注</p>
                    <p>3. 申请后可在"我的投递"中查看审核进度</p>
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

async function applyForJob(jobId) {
    if (!AppState.user) {
        showNotification('请先登录', 'error');
        return;
    }
    try {
        const data = await apiCall('/api/employment/apply', 'POST', {
            user_id: AppState.user.id,
            job_id: parseInt(jobId)
        });
        showNotification(data.message, data.success ? 'success' : 'error');
        if (data.success) {
            loadEmploymentStats();
            const el = document.getElementById('emp-points-balance');
            if (el) {
                const pts = await apiCall(`/api/employment/points/${AppState.user.id}`);
                if (pts.success) el.textContent = pts.points.toLocaleString();
            }
        }
    } catch(e) {
        showNotification('申请失败', 'error');
    }
}

async function toggleSaveJob(jobId, btnEl) {
    if (!AppState.user) {
        showNotification('请先登录', 'error');
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
        loadEmploymentStats();
    } catch(e) {
        showNotification('操作失败', 'error');
    }
}

async function loadEmploymentStats() {
    if (!AppState.user) return;
    try {
        const data = await apiCall(`/api/employment/stats/${AppState.user.id}`);
        if (data.success) {
            const s = data.stats;
            const el1 = document.getElementById('emp-stat-applied');
            const el2 = document.getElementById('emp-stat-saved');
            const el3 = document.getElementById('emp-stat-messages');
            if (el1) el1.textContent = s.applied;
            if (el2) el2.textContent = s.saved;
            if (el3) el3.textContent = s.messages;
        }
    } catch(e) {}
}

async function loadCertificateSummary() {
    if (!AppState.user) return;
    const container = document.getElementById('emp-cert-summary');
    if (!container) return;
    try {
        const data = await apiCall(`/api/employment/certificates/${AppState.user.id}`);
        if (data.success) {
            const certs = data.certificates;
            const earned = certs.filter(c => c.status === 'earned').length;
            const inProgress = certs.filter(c => c.status === 'in_progress').length;
            const total = certs.length;

            const summaryHeader = `
                <div class="emp-cert-summary-header">
                    <div class="emp-cert-stat-row">
                        <span class="emp-cert-earned-count">${earned}</span>
                        <span class="emp-cert-total-count">/${total}</span>
                        <span class="emp-cert-stat-label">已获得</span>
                    </div>
                    ${inProgress > 0 ? `<span class="emp-cert-inprogress-badge">${inProgress} 项进行中</span>` : ''}
                </div>`;

            const certList = certs.map(cert => {
                const statusClass = cert.status === 'earned' ? 'earned' : cert.status === 'locked' ? 'locked' : '';
                const statusIcon = cert.status === 'earned' ? 'fa-check-circle' : cert.status === 'locked' ? 'fa-lock' : 'fa-spinner';
                let detail = '';
                if (cert.status === 'earned') {
                    detail = `<div class="emp-cert-detail earned">获得于 ${cert.date || '--'}</div>`;
                } else if (cert.status === 'in_progress') {
                    detail = `
                        <div class="emp-cert-progress-wrap">
                            <div class="emp-cert-progress-bar">
                                <div class="emp-cert-progress-fill" style="width:${cert.progress}%"></div>
                            </div>
                            <span class="emp-cert-progress-text">${cert.progress}%</span>
                        </div>`;
                } else {
                    detail = `<div class="emp-cert-detail locked">完成相关课程可解锁</div>`;
                }
                return `
                <div class="emp-cert-mini ${statusClass}">
                    <div class="emp-cert-mini-icon ${statusClass}"><i class="fas ${statusIcon}"></i></div>
                    <div class="emp-cert-mini-body">
                        <div class="emp-cert-mini-name">${cert.name}</div>
                        ${detail}
                    </div>
                </div>`;
            }).join('');

            container.innerHTML = summaryHeader + certList + `
                <div class="emp-cert-footer">
                    <span class="emp-cert-footer-link" id="emp-cert-view-all">查看全部证书 <i class="fas fa-arrow-right"></i></span>
                </div>`;

            document.getElementById('emp-cert-view-all')?.addEventListener('click', () => {
                const CERT_DETAILS = {
                    '荔枝种植技术员': {
                        desc: '掌握荔枝全周期种植管理技术的专业认证，涵盖品种选育、水肥管理、病虫害防治、采收储运等核心技能。',
                        skills: ['荔枝品种识别与选育', '四季水肥管理方案', '霜疫霉病/炭疽病防治', '花果管理与保果技术', '采后保鲜与储运'],
                        benefits: ['优先获得农业合作社技术岗位', '享受农资采购优惠', '可申请农业技术推广员资格', '薪资溢价15%-25%'],
                        courses: ['荔枝春季管理实操', '荔枝病虫害识别与防治', '岭南水果采后处理技术'],
                        issuer: '广东省农业农村厅'
                    },
                    '电商运营师': {
                        desc: '具备电商平台全流程运营能力的认证，包括店铺搭建、产品上架、营销推广、数据分析、客户服务等核心技能。',
                        skills: ['淘宝/拼多多/抖音店铺运营', '产品详情页设计与优化', '直通车/巨量引擎推广', '直播带货策划与执行', '数据化运营分析'],
                        benefits: ['独立运营电商店铺', '可申请电商创业补贴', '对接平台官方资源', '薪资溢价20%-30%'],
                        courses: ['电商运营基础班', '直播带货实战训练', '短视频内容营销'],
                        issuer: '广东省商务厅'
                    },
                    '广绣工艺师': {
                        desc: '掌握国家级非物质文化遗产广绣技艺的专业认证，熟练运用直针、扭针、长短针、打籽针等核心针法，能独立完成作品创作。',
                        skills: ['直针/扭针/长短针/打籽针', '配色与渐变色绣制', '图案设计与转印', '上绷与绣布固定', '装裱与成品处理'],
                        benefits: ['非遗传承人认定资格', '工艺品销售渠道对接', '文创产品开发支持', '可开设个人工作室'],
                        courses: ['广绣基础针法入门', '广绣花卉绣制实操', '非遗传承人研修班'],
                        issuer: '广东省文化和旅游厅'
                    }
                };

                const detailHtml = certs.map(cert => {
                    const info = CERT_DETAILS[cert.name] || {};
                    const statusLabel = cert.status === 'earned' ? '已获得' : cert.status === 'in_progress' ? '学习中' : '未解锁';
                    const statusClass = cert.status === 'earned' ? 'earned' : cert.status === 'in_progress' ? 'progress' : 'locked';
                    const statusIcon = cert.status === 'earned' ? 'fa-check-circle' : cert.status === 'in_progress' ? 'fa-spinner' : 'fa-lock';

                    // 进度条
                    let progressHtml = '';
                    if (cert.status === 'in_progress') {
                        progressHtml = `
                            <div class="cert-detail-progress">
                                <div class="cert-detail-progress-bar">
                                    <div class="cert-detail-progress-fill" style="width:${cert.progress}%"></div>
                                </div>
                                <span class="cert-detail-progress-text">${cert.progress}%</span>
                            </div>`;
                    }

                    // 获得时间
                    let dateHtml = '';
                    if (cert.status === 'earned' && cert.date) {
                        dateHtml = `<div class="cert-detail-date"><i class="fas fa-calendar-check"></i> 获得时间：${cert.date}</div>`;
                    }

                    // 描述
                    let descHtml = '';
                    if (info.desc) {
                        descHtml = `<div class="cert-detail-desc">${info.desc}</div>`;
                    }

                    // 核心技能
                    let skillsHtml = '';
                    if (info.skills) {
                        skillsHtml = `
                            <div class="cert-detail-subsection">
                                <h5><i class="fas fa-cogs"></i> 核心技能</h5>
                                <div class="cert-detail-skills">
                                    ${info.skills.map(s => `<span class="cert-detail-skill-tag">${s}</span>`).join('')}
                                </div>
                            </div>`;
                    }

                    // 证书收益
                    let benefitsHtml = '';
                    if (info.benefits) {
                        benefitsHtml = `
                            <div class="cert-detail-subsection">
                                <h5><i class="fas fa-gift"></i> 证书收益</h5>
                                <div class="cert-detail-benefits">
                                    ${info.benefits.map(b => `<div class="cert-detail-benefit"><i class="fas fa-check-circle"></i>${b}</div>`).join('')}
                                </div>
                            </div>`;
                    }

                    // 推荐课程
                    let coursesHtml = '';
                    if (info.courses) {
                        coursesHtml = `
                            <div class="cert-detail-subsection">
                                <h5><i class="fas fa-book-open"></i> 推荐课程</h5>
                                <div class="cert-detail-courses">
                                    ${info.courses.map((c, i) => `
                                        <div class="cert-detail-course">
                                            <span class="cert-detail-course-num">${i + 1}</span>
                                            <span>${c}</span>
                                        </div>
                                    `).join('')}
                                </div>
                            </div>`;
                    }

                    // 发证机构
                    let issuerHtml = '';
                    if (info.issuer) {
                        issuerHtml = `<div class="cert-detail-issuer"><i class="fas fa-landmark"></i> 发证机构：${info.issuer}</div>`;
                    }

                    // 解锁提示
                    let unlockHtml = '';
                    if (cert.status === 'locked') {
                        unlockHtml = `
                            <div class="cert-detail-unlock">
                                <i class="fas fa-info-circle"></i>
                                <span>完成上方推荐课程即可解锁此证书，获得对应职业技能认证。</span>
                            </div>`;
                    }

                    return `
                        <div class="cert-detail-card ${statusClass}">
                            <div class="cert-detail-card-header">
                                <div class="cert-detail-icon ${statusClass}">
                                    <i class="fas ${statusIcon}"></i>
                                </div>
                                <div class="cert-detail-title-area">
                                    <h3 class="cert-detail-name">${cert.name}</h3>
                                    <span class="cert-detail-status ${statusClass}">${statusLabel}${cert.status === 'in_progress' ? ` · ${cert.progress}%` : ''}</span>
                                </div>
                            </div>
                            ${dateHtml}
                            ${progressHtml}
                            ${descHtml}
                            ${skillsHtml}
                            ${benefitsHtml}
                            ${coursesHtml}
                            ${issuerHtml}
                            ${unlockHtml}
                        </div>`;
                }).join('');

                showDetailModal('我的技能证书', `<div class="cert-detail-list">${detailHtml}</div>`);
            });
        }
    } catch(e) {
        container.innerHTML = '<p style="font-size:0.85rem;color:var(--text-muted);">加载失败</p>';
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
                listEl.innerHTML = data.applications.map(app => renderApplicationCard(app)).join('');
            }
        }
    } catch(e) {
        showErrorState(listEl, '加载投递记录失败', () => loadUserApplications(statusFilter));
    }
}

function renderApplicationCard(app) {
    const statusMap = {
        'pending': { text: '待审核', class: 'pending' },
        'approved': { text: '已通过', class: 'approved' },
        'rejected': { text: '已拒绝', class: 'rejected' }
    };
    const status = statusMap[app.status] || statusMap.pending;
    const timelineSteps = [
        { label: `投递简历 ${app.applied_at || ''}`, done: true },
        { label: '简历审核中', done: app.status !== 'pending', active: app.status === 'pending' },
        { label: app.status === 'approved' ? '已通过审核' : app.status === 'rejected' ? '未通过审核' : '面试安排', done: app.status === 'approved' || app.status === 'rejected', active: false }
    ];
    if (app.status === 'approved') timelineSteps[2].done = true;

    return `
    <div class="emp-app-card">
        <div class="emp-app-header">
            <h4>${app.title}</h4>
            <span class="emp-app-status ${status.class}">${status.text}</span>
        </div>
        <p class="emp-app-company">${app.company} · ${app.location || '广东'}</p>
        <p class="emp-app-salary">${app.salary}</p>
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
    if (!AppState.user) return;
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

    // 作业管理
    document.getElementById('teacher-create-assignment-btn')?.addEventListener('click', showCreateAssignmentModal);

    // 签到考勤
    document.getElementById('teacher-start-attendance-btn')?.addEventListener('click', startAttendance);
}

function showAddStudentModal() {
    showDetailModal('添加学员', `
        <div class="teacher-form">
            <div class="form-group">
                <label>学员姓名</label>
                <input type="text" id="new-student-name" placeholder="输入姓名">
            </div>
            <div class="form-group">
                <label>班级</label>
                <input type="text" id="new-student-class" placeholder="例如：2024春季班" value="2024春季班">
            </div>
            <div class="form-group">
                <label>学习方向</label>
                <select id="new-student-direction">
                    <option value="荔枝种植">荔枝种植</option>
                    <option value="电商运营">电商运营</option>
                    <option value="广绣工艺">广绣工艺</option>
                    <option value="水产养殖">水产养殖</option>
                </select>
            </div>
            <button class="btn btn-primary teacher-form-submit" id="submit-add-student">
                <i class="fas fa-plus"></i> 确认添加
            </button>
        </div>
    `);
    document.getElementById('submit-add-student')?.addEventListener('click', async () => {
        const name = document.getElementById('new-student-name').value.trim();
        const class_name = document.getElementById('new-student-class').value;
        const direction = document.getElementById('new-student-direction').value;
        if (!name) { showNotification('请输入姓名', 'error'); return; }
        try {
            const data = await apiCall('/api/teacher/students/add', 'POST', { name, class_name, direction });
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
    showDetailModal(`编辑学员 - ${student.name}`, `
        <div class="teacher-form">
            <div class="form-group">
                <label>学员姓名</label>
                <input type="text" id="edit-student-name" value="${student.name}">
            </div>
            <div class="form-group">
                <label>班级</label>
                <input type="text" id="edit-student-class" value="${student.class_name || ''}">
            </div>
            <div class="form-group">
                <label>学习方向</label>
                <select id="edit-student-direction">
                    ${['荔枝种植','电商运营','广绣工艺','水产养殖'].map(d =>
                        `<option value="${d}" ${d === student.direction ? 'selected' : ''}>${d}</option>`
                    ).join('')}
                </select>
            </div>
            <div class="form-group">
                <label>学习进度 (0-100)</label>
                <input type="number" id="edit-student-progress" min="0" max="100" value="${student.progress}">
            </div>
            <div class="teacher-form-actions">
                <button class="btn btn-outline" id="cancel-edit-student">取消</button>
                <button class="btn btn-primary" id="submit-edit-student">
                    <i class="fas fa-check"></i> 保存修改
                </button>
            </div>
        </div>
    `);
    document.getElementById('cancel-edit-student')?.addEventListener('click', () => {
        document.querySelector('.modal-overlay.detail-modal')?.remove();
    });
    document.getElementById('submit-edit-student')?.addEventListener('click', async () => {
        const name = document.getElementById('edit-student-name').value.trim();
        if (!name) { showNotification('请输入姓名', 'error'); return; }
        try {
            const data = await apiCall(`/api/teacher/students/${student.id}`, 'PUT', {
                name,
                class_name: document.getElementById('edit-student-class').value,
                direction: document.getElementById('edit-student-direction').value,
                progress: parseInt(document.getElementById('edit-student-progress').value) || 0
            });
            showNotification(data.message, data.success ? 'success' : 'error');
            if (data.success) {
                document.querySelector('.modal-overlay.detail-modal')?.remove();
                loadStudents();
                loadTeacherDashboard();
            }
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
            // 动态
            renderActivities(data.dashboard.recent_activities);
        }
        loadStudents();
    } catch(e) {
        Object.values(statEls).forEach(el => { if (el) el.textContent = '-'; });
    }
}

function renderActivities(activities) {
    const list = document.getElementById('teacher-activity-list');
    if (!list || !activities) return;
    const icons = {
        student_join: { icon: 'fa-user-plus', color: '#0ea5e9' },
        certificate_earned: { icon: 'fa-award', color: '#10b981' },
        progress_update: { icon: 'fa-chart-line', color: '#f59e0b' }
    };
    list.innerHTML = activities.map(a => {
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
                    <td><span class="teacher-student-name">${s.name}</span></td>
                    <td><span class="teacher-direction-tag">${s.direction}</span></td>
                    <td>
                        <div class="teacher-progress-cell">
                            <div class="progress-bar small"><div class="progress-fill" style="width:${s.progress}%"></div></div>
                            <span class="teacher-progress-text">${s.progress}%</span>
                        </div>
                    </td>
                    <td><span class="cert-badge ${s.progress >= 100 ? '' : 'pending'}">${s.progress >= 100 ? '已获得' : '学习中'}</span></td>
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
        const progressColor = st.progress >= 80 ? '#10b981' : st.progress >= 50 ? '#f59e0b' : '#ef4444';
        showDetailModal(`学员详情`, `
            <div class="teacher-detail">
                <div class="teacher-detail-header">
                    <div class="teacher-detail-avatar">${st.name.charAt(0)}</div>
                    <div class="teacher-detail-info">
                        <div class="teacher-detail-name">${st.name}</div>
                        <div class="teacher-detail-id">${st.id} · ${st.class_name || '未分班'}</div>
                    </div>
                    <span class="cert-badge ${st.progress >= 100 ? '' : 'pending'}">${st.progress >= 100 ? '已毕业' : '学习中'}</span>
                </div>
                <div class="teacher-detail-stats">
                    <div class="teacher-detail-stat">
                        <span class="teacher-detail-stat-label">学习方向</span>
                        <span class="teacher-detail-stat-value">${st.direction}</span>
                    </div>
                    <div class="teacher-detail-stat">
                        <span class="teacher-detail-stat-label">学习进度</span>
                        <span class="teacher-detail-stat-value" style="color:${progressColor}">${st.progress}%</span>
                    </div>
                    <div class="teacher-detail-stat">
                        <span class="teacher-detail-stat-label">状态</span>
                        <span class="teacher-detail-stat-value">${st.status === 'active' ? '在读' : st.status}</span>
                    </div>
                </div>
                <div class="teacher-detail-progress-bar">
                    <div class="progress-bar"><div class="progress-fill" style="width:${st.progress}%; background:${progressColor}"></div></div>
                </div>
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
    showDetailModal('<i class="fas fa-wand-magic-sparkles"></i> AI 教学报告', `
        <div class="report-modal-body">
            <div class="report-loading">
                <div class="spinner"></div>
                <p>AI 正在分析学员数据并生成报告...</p>
                <span class="report-loading-hint">这可能需要几秒钟，请耐心等待</span>
            </div>
        </div>
    `);

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
                    avg_progress: { value: ov.avg_progress + '%', label: '平均进度', cls: 'accent' },
                    direction_count: { value: ov.direction_count, label: '学习方向', cls: '' },
                    completed_count: { value: ov.completed_count, label: '已完成', cls: 'success' },
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
                                            <div class="report-risk-bar-fill" style="width:${s.progress}%;background:${s.progress < 15 ? '#ef4444' : '#f59e0b'}"></div>
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
    navigator.clipboard.writeText(text).then(() => {
        showNotification('报告内容已复制', 'success');
    }).catch(() => {
        showNotification('复制失败', 'error');
    });
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
            else if (tab === 'assignments') loadAssignments();
            else if (tab === 'attendance') loadAttendances();
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

// ==================== 作业管理 ====================

async function loadAssignments() {
    const container = document.getElementById('teacher-assignments-list');
    if (!container) return;
    container.innerHTML = '<div class="teacher-loading"><div class="spinner"></div> 加载中...</div>';
    try {
        const data = await apiCall('/api/teacher/assignments');
        if (!data.success || !data.assignments.length) {
            container.innerHTML = '<div class="teacher-empty"><i class="fas fa-book-open"></i><p>暂无作业</p></div>';
            return;
        }
        container.innerHTML = data.assignments.map(a => `
            <div class="assignment-card" onclick="openAssignmentDetail(${a.id})">
                <div class="assignment-card-header">
                    <span class="assignment-direction">${a.direction || '通用'}</span>
                    <span class="assignment-deadline">${a.deadline ? '截止: ' + a.deadline : '无截止日期'}</span>
                </div>
                <h4 class="assignment-title">${a.title}</h4>
                <p class="assignment-desc">${a.description || '暂无描述'}</p>
                <div class="assignment-stats">
                    <span><i class="fas fa-users"></i> 提交 ${a.submission_count || 0}</span>
                    <span><i class="fas fa-check"></i> 已批 ${a.graded_count || 0}</span>
                    <span><i class="fas fa-star"></i> 满分 ${a.total_score}</span>
                </div>
            </div>
        `).join('');
    } catch(e) {
        container.innerHTML = '<div class="teacher-error">加载失败</div>';
    }
}

function showCreateAssignmentModal() {
    showDetailModal('发布作业', `
        <div class="teacher-form">
            <div class="form-group">
                <label>作业标题</label>
                <input type="text" id="asgn-title" placeholder="输入作业标题">
            </div>
            <div class="form-group">
                <label>学习方向</label>
                <select id="asgn-direction">
                    <option value="">通用</option>
                    <option value="荔枝种植">荔枝种植</option>
                    <option value="电商运营">电商运营</option>
                    <option value="广绣工艺">广绣工艺</option>
                    <option value="水产养殖">水产养殖</option>
                </select>
            </div>
            <div class="form-group">
                <label>截止日期</label>
                <input type="datetime-local" id="asgn-deadline">
            </div>
            <div class="form-group">
                <label>满分分值</label>
                <input type="number" id="asgn-score" value="100" min="1" max="1000">
            </div>
            <div class="form-group">
                <label>作业描述</label>
                <textarea id="asgn-desc" rows="4" placeholder="输入作业要求和描述"></textarea>
            </div>
            <button class="btn btn-primary teacher-form-submit" id="submit-assignment">
                <i class="fas fa-paper-plane"></i> 发布作业
            </button>
        </div>
    `);
    document.getElementById('submit-assignment')?.addEventListener('click', async () => {
        const title = document.getElementById('asgn-title').value.trim();
        const description = document.getElementById('asgn-desc').value.trim();
        const direction = document.getElementById('asgn-direction').value;
        const deadline = document.getElementById('asgn-deadline').value;
        const total_score = parseInt(document.getElementById('asgn-score').value) || 100;
        if (!title) { showNotification('请填写作业标题', 'error'); return; }
        try {
            const data = await apiCall('/api/teacher/assignments', 'POST', { title, description, direction, deadline, total_score });
            showNotification(data.message, data.success ? 'success' : 'error');
            if (data.success) {
                document.querySelector('.modal-overlay.detail-modal')?.remove();
                loadAssignments();
            }
        } catch(e) {
            showNotification('发布失败', 'error');
        }
    });
}

async function openAssignmentDetail(id) {
    try {
        const data = await apiCall('/api/teacher/assignments/' + id);
        if (!data.success) return;
        const a = data.assignment;
        const submissions = data.submissions || [];
        let submissionsHtml = '';
        if (submissions.length) {
            submissionsHtml = `
                <table class="teacher-table submissions-table">
                    <thead><tr>
                        <th>学员ID</th><th>提交时间</th><th>状态</th><th>分数</th><th>操作</th>
                    </tr></thead>
                    <tbody>
                        ${submissions.map(s => `<tr>
                            <td>${s.student_id}</td>
                            <td>${s.submitted_at || '-'}</td>
                            <td><span class="status-badge status-${s.status}">${s.status === 'graded' ? '已批改' : '待批改'}</span></td>
                            <td>${s.score != null ? s.score + '/' + a.total_score : '-'}</td>
                            <td>
                                ${s.status !== 'graded' ? `<button class="btn btn-primary btn-xs" onclick="gradeSubmission(${s.id}, ${a.total_score})"><i class="fas fa-pen"></i> 批改</button>` : '<span class="text-muted">已完成</span>'}
                            </td>
                        </tr>`).join('')}
                    </tbody>
                </table>`;
        } else {
            submissionsHtml = '<div class="teacher-empty"><i class="fas fa-inbox"></i><p>暂无提交</p></div>';
        }
        showDetailModal(a.title, `
            <div class="assignment-detail">
                <div class="assignment-detail-info">
                    <p><strong>方向：</strong>${a.direction || '通用'}</p>
                    <p><strong>截止日期：</strong>${a.deadline || '无'}</p>
                    <p><strong>满分：</strong>${a.total_score}</p>
                    <p><strong>描述：</strong>${a.description || '暂无'}</p>
                </div>
                <h4 style="margin-top:16px">提交列表</h4>
                ${submissionsHtml}
            </div>
        `);
    } catch(e) {
        showNotification('加载失败', 'error');
    }
}

function gradeSubmission(submissionId, totalScore) {
    // 关闭当前详情弹窗，打开批改弹窗
    document.querySelector('.modal-overlay.detail-modal')?.remove();
    showDetailModal('批改作业', `
        <div class="teacher-form">
            <div class="form-group">
                <label>分数 (满分 ${totalScore})</label>
                <input type="number" id="grade-score" min="0" max="${totalScore}" placeholder="输入分数">
            </div>
            <div class="form-group">
                <label>评语</label>
                <textarea id="grade-feedback" rows="4" placeholder="输入评语（可选）"></textarea>
            </div>
            <button class="btn btn-primary teacher-form-submit" id="submit-grade">
                <i class="fas fa-check"></i> 确认批改
            </button>
        </div>
    `);
    document.getElementById('submit-grade')?.addEventListener('click', async () => {
        const score = parseInt(document.getElementById('grade-score').value);
        const feedback = document.getElementById('grade-feedback').value.trim();
        if (isNaN(score) || score < 0) { showNotification('请输入有效分数', 'error'); return; }
        try {
            const data = await apiCall('/api/teacher/assignments/grade', 'POST', {
                submission_id: submissionId, score, feedback
            });
            showNotification(data.message, data.success ? 'success' : 'error');
            if (data.success) {
                document.querySelector('.modal-overlay.detail-modal')?.remove();
                loadAssignments();
            }
        } catch(e) {
            showNotification('批改失败', 'error');
        }
    });
}

// ==================== 签到考勤 ====================

async function loadAttendances() {
    const container = document.getElementById('teacher-attendance-list');
    if (!container) return;
    container.innerHTML = '<div class="teacher-loading"><div class="spinner"></div> 加载中...</div>';
    try {
        const data = await apiCall('/api/teacher/attendance');
        if (!data.success || !data.attendances.length) {
            container.innerHTML = '<div class="teacher-empty"><i class="fas fa-clipboard-check"></i><p>暂无签到记录</p></div>';
            return;
        }
        container.innerHTML = data.attendances.map(a => `
            <div class="attendance-card">
                <div class="attendance-header">
                    <h4 class="attendance-title">${a.title}</h4>
                    <span class="attendance-status-badge ${a.status === 'open' ? 'status-open' : 'status-closed'}">
                        ${a.status === 'open' ? '进行中' : '已结束'}
                    </span>
                </div>
                <div class="attendance-meta">
                    <span><i class="fas fa-clock"></i> ${a.created_at}</span>
                    <span><i class="fas fa-users"></i> 出勤 ${a.checkin_count || 0} / ${a.total_students || 0}</span>
                </div>
                <div class="attendance-actions">
                    ${a.status === 'open' ? `<button class="btn btn-danger btn-xs" onclick="closeAttendance(${a.id})"><i class="fas fa-stop"></i> 结束签到</button>` : ''}
                    <button class="btn btn-outline btn-xs" onclick="openAttendanceDetail(${a.id})"><i class="fas fa-list"></i> 查看详情</button>
                </div>
            </div>
        `).join('');
    } catch(e) {
        container.innerHTML = '<div class="teacher-error">加载失败</div>';
    }
}

async function startAttendance() {
    const title = prompt('签到标题：', '日常签到');
    if (!title) return;
    try {
        const data = await apiCall('/api/teacher/attendance', 'POST', { title });
        showNotification(data.message, data.success ? 'success' : 'error');
        if (data.success) loadAttendances();
    } catch(e) {
        showNotification('发起签到失败', 'error');
    }
}

async function closeAttendance(id) {
    if (!confirm('确定结束此次签到？')) return;
    try {
        const data = await apiCall('/api/teacher/attendance/close', 'POST', { attendance_id: id });
        showNotification(data.message, data.success ? 'success' : 'error');
        if (data.success) loadAttendances();
    } catch(e) {
        showNotification('操作失败', 'error');
    }
}

async function openAttendanceDetail(id) {
    try {
        const data = await apiCall('/api/teacher/attendance/' + id);
        if (!data.success) return;
        const records = data.records || [];
        let recordsHtml = '';
        if (records.length) {
            recordsHtml = `
                <table class="teacher-table">
                    <thead><tr><th>学员ID</th><th>状态</th><th>签到时间</th></tr></thead>
                    <tbody>
                        ${records.map(r => `<tr>
                            <td>${r.student_id}</td>
                            <td><span class="status-badge status-${r.check_status}">${r.check_status === 'present' ? '已签到' : r.check_status === 'late' ? '迟到' : '缺勤'}</span></td>
                            <td>${r.checked_at || '-'}</td>
                        </tr>`).join('')}
                    </tbody>
                </table>`;
        } else {
            recordsHtml = '<div class="teacher-empty"><i class="fas fa-user-slash"></i><p>暂无签到记录</p></div>';
        }
        showDetailModal('签到详情', recordsHtml);
    } catch(e) {
        showNotification('加载失败', 'error');
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
        container.innerHTML = `
            <div class="analytics-section">
                <h4 class="analytics-section-title"><i class="fas fa-chart-bar"></i> 学习进度分布</h4>
                <div class="analytics-chart" id="progress-chart"></div>
            </div>
            <div class="analytics-section">
                <h4 class="analytics-section-title"><i class="fas fa-chart-pie"></i> 方向分布</h4>
                <div class="analytics-chart" id="direction-chart"></div>
            </div>
            <div class="analytics-section">
                <h4 class="analytics-section-title"><i class="fas fa-table"></i> 各方向进度详情</h4>
                <div id="direction-detail"></div>
            </div>
        `;
        renderProgressChart(data.progress_distribution || []);
        renderDirectionChart(data.direction_distribution || []);
        renderDirectionDetail(data.direction_progress || []);
    } catch(e) {
        container.innerHTML = '<div class="teacher-error">加载失败</div>';
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
                    <div class="bar-label">${d.range}</div>
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
    const colors = ['#00b4d8','#ff6b6b','#ffd93d','#6bcb77','#9b59b6','#e67e22'];
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
    el.innerHTML = `
        <table class="teacher-table">
            <thead><tr><th>方向</th><th>学员数</th><th>平均进度</th><th>平均成绩</th></tr></thead>
            <tbody>
                ${data.map(d => `<tr>
                    <td>${d.direction}</td>
                    <td>${d.student_count}</td>
                    <td>${(d.avg_progress || 0).toFixed(1)}%</td>
                    <td>${(d.avg_score || 0).toFixed(1)}</td>
                </tr>`).join('')}
            </tbody>
        </table>
    `;
}

// ==================== 3D播放控制 ====================

function setup3DControls() {
    document.getElementById('slow-play')?.addEventListener('click', () => showNotification('已切换到慢放模式', 'info'));
    document.getElementById('pause-play')?.addEventListener('click', () => showNotification('已暂停播放', 'info'));
    document.getElementById('multi-angle')?.addEventListener('click', () => showNotification('已切换多角度视图', 'info'));
}

// ==================== 消息通知 ====================

function setupQuickMessage() {
    const btn = document.getElementById('quick-message-btn');
    const dropdown = document.getElementById('msg-dropdown');
    if (!btn || !dropdown) return;

    // 铃铛点击切换下拉面板
    btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const isOpen = dropdown.classList.toggle('show');
        if (isOpen) {
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
    try {
        const userId = AppState.currentUser?.id || AppState.sessionId || '';
        if (!userId) return;
        const [notifRes, msgRes] = await Promise.all([
            apiCall(`/api/notifications/unread?user_id=${userId}`),
            apiCall(`/api/messages/unread?user_id=${userId}`)
        ]);
        const total = (notifRes.count || 0) + (msgRes.count || 0);
        badge.textContent = total;
        badge.classList.toggle('is-hidden', total === 0);
    } catch(e) {}
}

async function loadNotifications() {
    const container = document.getElementById('msg-notifications-list');
    if (!container) return;
    const userId = AppState.currentUser?.id || AppState.sessionId || '';
    if (!userId) { container.innerHTML = '<div class="msg-empty">请先登录</div>'; return; }
    try {
        const data = await apiCall(`/api/notifications?user_id=${userId}`);
        if (!data.success || !data.notifications.length) {
            container.innerHTML = '<div class="msg-empty"><i class="fas fa-bell-slash"></i><p>暂无通知</p></div>';
            return;
        }
        container.innerHTML = data.notifications.map(n => {
            const iconMap = {
                'announcement': 'fa-bullhorn',
                'assignment': 'fa-book-open',
                'attendance': 'fa-clipboard-check',
                'grade': 'fa-star',
                'system': 'fa-gear'
            };
            const icon = iconMap[n.type] || 'fa-bell';
            const time = formatTimeAgo(n.created_at);
            return `
                <div class="msg-item ${n.is_read ? '' : 'unread'}" data-id="${n.id}">
                    <div class="msg-item-icon type-${n.type}"><i class="fas ${icon}"></i></div>
                    <div class="msg-item-text">
                        <div class="msg-item-title">${n.title}</div>
                        <div class="msg-item-preview">${n.content || ''}</div>
                        <div class="msg-item-time">${time}</div>
                    </div>
                </div>
            `;
        }).join('');
    } catch(e) {
        container.innerHTML = '<div class="msg-empty">加载失败</div>';
    }
}

async function loadConversations() {
    const container = document.getElementById('msg-messages-list');
    if (!container) return;
    const userId = AppState.currentUser?.id || AppState.sessionId || '';
    if (!userId) { container.innerHTML = '<div class="msg-empty">请先登录</div>'; return; }
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

    const myId = AppState.currentUser?.id || AppState.sessionId || '';
    if (!myId) return;

    // 加载会话消息
    let messages = [];
    try {
        const data = await apiCall(`/api/messages/conversation/${userId}?user_id=${myId}`);
        if (data.success) messages = data.messages;
    } catch(e) {}

    showDetailModal(`<i class="fas fa-envelope"></i> 与 ${userName} 的对话`, `
        <div class="conversation-modal">
            <div class="conversation-messages" id="conversation-messages">
                ${messages.length ? messages.map(m => `
                    <div class="msg-bubble ${m.sender_id === myId ? 'mine' : 'theirs'}">
                        <div class="msg-bubble-content">${m.content}</div>
                        <div class="msg-bubble-time">${m.created_at ? m.created_at.slice(11, 16) : ''}</div>
                    </div>
                `).join('') : '<div class="msg-empty">暂无消息，发送第一条吧</div>'}
            </div>
            <div class="conversation-input">
                <input type="text" id="conversation-msg-input" placeholder="输入消息..." maxlength="500">
                <button class="btn btn-primary btn-sm" id="conversation-send-btn">
                    <i class="fas fa-paper-plane"></i>
                </button>
            </div>
        </div>
    `);

    // 滚动到底部
    const msgContainer = document.getElementById('conversation-messages');
    if (msgContainer) msgContainer.scrollTop = msgContainer.scrollHeight;

    // 发送按钮
    const sendBtn = document.getElementById('conversation-send-btn');
    const input = document.getElementById('conversation-msg-input');

    async function doSend() {
        const content = input?.value.trim();
        if (!content) return;
        try {
            await apiCall('/api/messages/send', 'POST', {
                sender_id: myId, receiver_id: userId, content
            });
            // 添加气泡
            const bubble = document.createElement('div');
            bubble.className = 'msg-bubble mine';
            bubble.innerHTML = `<div class="msg-bubble-content">${content}</div><div class="msg-bubble-time">${new Date().toTimeString().slice(0,5)}</div>`;
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
    const userId = AppState.currentUser?.id || AppState.sessionId || '';
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
    const userId = AppState.currentUser?.id || AppState.sessionId || '';
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

    // 获取学员列表作为收件人选项
    let students = [];
    try {
        const data = await apiCall('/api/teacher/students');
        if (data.success) students = data.students;
    } catch(e) {}

    showDetailModal('<i class="fas fa-pen"></i> 写消息', `
        <div class="teacher-form">
            <div class="form-group">
                <label>收件人</label>
                <select id="compose-receiver">
                    <option value="">选择收件人</option>
                    ${students.map(s => `<option value="${s.id}">${s.name}（${s.direction}）</option>`).join('')}
                </select>
            </div>
            <div class="form-group">
                <label>消息内容</label>
                <textarea id="compose-content" rows="4" placeholder="输入消息内容..." maxlength="500"></textarea>
            </div>
            <button class="btn btn-primary teacher-form-submit" id="compose-send-btn">
                <i class="fas fa-paper-plane"></i> 发送
            </button>
        </div>
    `);

    document.getElementById('compose-send-btn')?.addEventListener('click', async () => {
        const receiverId = document.getElementById('compose-receiver')?.value;
        const content = document.getElementById('compose-content')?.value.trim();
        const senderId = AppState.currentUser?.id || AppState.sessionId || '';
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

// ==================== 积分兑换 ====================

function setupPointsExchange() {
    document.querySelectorAll('.exchange-item').forEach(item => {
        item.style.cursor = 'pointer';
        item.addEventListener('click', async () => {
            if (!AppState.user) {
                showNotification('请先登录', 'error');
                return;
            }
            const name = item.querySelector('.exchange-item-name')?.textContent || item.querySelector('span:nth-child(2)')?.textContent || '';
            const cost = parseInt(item.querySelector('.points-cost')?.textContent) || 0;
            try {
                const data = await apiCall('/api/employment/exchange', 'POST', {
                    user_id: AppState.user.id,
                    item: name, cost
                });
                if (data.success) {
                    const pts = data.remaining_points.toLocaleString();
                    const el1 = document.getElementById('points-balance');
                    const el2 = document.getElementById('emp-points-balance');
                    if (el1) el1.textContent = pts;
                    if (el2) el2.textContent = pts;
                    showNotification(data.message, 'success');
                } else {
                    showNotification(data.message, 'error');
                }
            } catch(e) {
                showNotification('兑换失败', 'error');
            }
        });
    });
}

// ==================== 通用详情模态框 ====================

function showDetailModal(title, html) {
    // 移除已有的
    document.querySelector('.modal-overlay.detail-modal')?.remove();

    const modal = document.createElement('div');
    modal.className = 'modal-overlay detail-modal';
    modal.style.display = 'flex';
    modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-modal', 'true');
    modal.setAttribute('aria-labelledby', 'detail-modal-title');
    modal.innerHTML = `
        <div class="modal-content">
            <div class="modal-header">
                <h3 id="detail-modal-title">${escapeHtml(title)}</h3>
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

function showNotification(message, type = 'info') {
    const notification = document.getElementById('notification');
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
    notification.classList.add('show');
    setTimeout(() => notification.classList.remove('show'), 3000);
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
    const statNumbers = document.querySelectorAll('.stat-number[data-target]');
    if (statNumbers.length === 0) return;

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const el = entry.target;
                const target = parseInt(el.getAttribute('data-target'));
                if (prefersReducedMotion) {
                    el.textContent = target.toLocaleString();
                } else {
                    animateNumber(el, target);
                }
                observer.unobserve(el);
            }
        });
    }, { threshold: 0.5 });

    statNumbers.forEach(el => observer.observe(el));
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
            el.textContent = target.toLocaleString() + '+';
        }
    }

    requestAnimationFrame(update);
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
