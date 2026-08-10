/* ============================================================
   粤乡智匠 — 门户通用脚本 (portal.js)
   四个角色门户共享：会话检查、登出、侧栏导航、汉堡菜单
   依赖: js/core.js (先于本文件加载)
   ============================================================ */

window.PORTAL = window.PORTAL || {};

// ---- 会话初始化 ----
PORTAL.init = function(expectedRole, userNameElId, onReady) {
    var saved = localStorage.getItem('yuexiang_session');
    if (!saved) { location.href = 'index.html'; return; }
    try {
        var data = JSON.parse(saved);
        AppState.sessionId = data.sessionId;
        AppState.user = data.user;
    } catch (e) {
        location.href = 'index.html';
        return;
    }
    if (AppState.user.role !== expectedRole) {
        location.href = 'index.html';
        return;
    }
    // 显示用户名
    if (userNameElId) {
        var el = document.getElementById(userNameElId);
        if (el) el.textContent = AppState.user.name || AppState.user.username;
    }
    // 绑定侧栏导航
    PORTAL.bindNav();
    // 绑定汉堡菜单
    PORTAL.bindHamburger();
    // 回调
    if (typeof onReady === 'function') onReady();
};

// ---- 登出 ----
PORTAL.logout = function() {
    apiCall('/api/auth/logout', 'POST', { session_id: AppState.sessionId });
    localStorage.removeItem('yuexiang_session');
    location.href = 'index.html';
};

// ---- 侧栏导航切换 ----
PORTAL.bindNav = function() {
    document.querySelectorAll('.portal-sidebar nav a').forEach(function(link) {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            // 激活态
            document.querySelectorAll('.portal-sidebar nav a').forEach(function(x) {
                x.classList.remove('active');
            });
            this.classList.add('active');

            var pageName = this.dataset.page;
            // 切换页面
            document.querySelectorAll('.page').forEach(function(p) {
                p.classList.remove('active');
            });
            var target = document.getElementById('page-' + pageName);
            if (target) target.classList.add('active');

            // 更新标题
            var titleEl = document.getElementById('page-title');
            if (titleEl) titleEl.textContent = this.textContent.trim();

            // 关闭移动端侧栏
            PORTAL.closeSidebar();

            // 触发页面加载回调
            if (PORTAL._onPageChange) PORTAL._onPageChange(pageName);
        });
    });
};

// ---- 页面切换回调注册 ----
PORTAL.onPageChange = function(fn) {
    PORTAL._onPageChange = fn;
};

// ---- 汉堡菜单（移动端） ----
PORTAL.bindHamburger = function() {
    var btn = document.getElementById('hamburger-portal');
    if (!btn) return;
    var sidebar = document.querySelector('.portal-sidebar');
    var overlay = document.getElementById('sidebar-overlay');
    btn.addEventListener('click', function() {
        sidebar.classList.toggle('open');
        if (overlay) overlay.classList.toggle('show');
    });
    if (overlay) {
        overlay.addEventListener('click', function() {
            sidebar.classList.remove('open');
            overlay.classList.remove('show');
        });
    }
};

PORTAL.closeSidebar = function() {
    var sidebar = document.querySelector('.portal-sidebar');
    var overlay = document.getElementById('sidebar-overlay');
    if (sidebar) sidebar.classList.remove('open');
    if (overlay) overlay.classList.remove('show');
};
