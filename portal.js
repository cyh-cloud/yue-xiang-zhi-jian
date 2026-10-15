/* ============================================================
   粤乡智匠 — 门户通用脚本 (portal.js)
   各角色门户共享：会话检查、登出、侧栏导航、按能力显隐、汉堡菜单
   依赖: js/core.js (先于本文件加载)

   2026-10-15（T13）：PORTAL.init 的第一个参数从「单个角色」改为「角色白名单」，
   数组或单字符串都收。此前 operator 打开 operator.html 会被踢回首页 ——
   门户页从此按「哪些角色能进」声明，而不是「唯一角色是谁」。

   导航与入口的显隐改按**能力**判定（PORTAL.applyCapabilities），不按角色名：
   能力清单由后端随登录下发（/api/auth/login 的 capabilities 字段），
   前端不复制一份能力表。标了 data-capability 的元素，会话不持该能力就隐藏。
   ============================================================ */

window.PORTAL = window.PORTAL || {};

// ---- 会话初始化 ----
// expectedRoles：允许进入本页的角色。字符串（单角色，历史形状）或数组都收。
PORTAL.init = function(expectedRoles, userNameElId, onReady) {
    var saved = localStorage.getItem('yuexiang_session');
    if (!saved) { location.href = 'index.html'; return; }
    try {
        var data = JSON.parse(saved);
        AppState.sessionId = data.sessionId;
        AppState.user = data.user;
        // 能力清单可能来自旧的本地会话（登录早于本次改动），补一次拉取兜底。
        AppState.capabilities = data.capabilities || [];
    } catch (e) {
        location.href = 'index.html';
        return;
    }
    var allowed = (typeof expectedRoles === 'string') ? [expectedRoles] : expectedRoles;
    if (!allowed || allowed.indexOf(AppState.user.role) < 0) {
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
    // 按能力显隐导航项与入口（本地没有清单时才需要发请求）
    PORTAL.applyCapabilities(function() {
        // 回调
        if (typeof onReady === 'function') onReady();
    });
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
            if (overlay) overlay.classList.remove('show');
        });
    }
};

PORTAL.closeSidebar = function() {
    var sidebar = document.querySelector('.portal-sidebar');
    var overlay = document.getElementById('sidebar-overlay');
    if (sidebar) sidebar.classList.remove('open');
    if (overlay) overlay.classList.remove('show');
};

// ---- 能力显隐 ----
// 会话持有的能力清单。登录/校验时由后端下发，不在此处复制一份能力表
// （单一真相源：能力与角色的对应只在 backend/core/permissions.py）。
// can() 是 fail-closed 的后端缩小版：清单里没有的一律视为不持有。
PORTAL.capabilities = function() {
    var list = (AppState && AppState.capabilities) || [];
    return Array.isArray(list) ? list : [];
};

PORTAL.can = function(capability) {
    return PORTAL.capabilities().indexOf(capability) >= 0;
};

// 本地没有能力清单时（旧会话、或登录接口还没下发）向后端补取一次。
// 拉取失败不阻塞页面：显隐退化成「只显示无 data-capability 的常驻项」，
// 与后端 fail-closed 的取向一致 —— 宁可少给入口，不多给。
PORTAL.applyCapabilities = function(onDone) {
    if (PORTAL.capabilities().length || !AppState.sessionId) {
        PORTAL.applyCapabilityVisibility();
        if (typeof onDone === 'function') onDone();
        return;
    }
    fetch((window.APP_CONFIG && window.APP_CONFIG.apiBaseUrl || '') + '/api/auth/capabilities', {
        headers: { 'X-Session-Id': AppState.sessionId }
    }).then(function(r) { return r.json(); }).then(function(body) {
        if (body && body.success) {
            AppState.capabilities = body.capabilities || [];
        }
    }).catch(function() {
        // 静默：上面已说明失败时的降级行为
    }).then(function() {
        PORTAL.applyCapabilityVisibility();
        if (typeof onDone === 'function') onDone();
    });
};

// 按 data-capability 显隐。写法：<a data-page="users" data-capability="user.manage">。
// 没有 data-capability 的元素不受影响（例如「仪表盘」对所有进门角色都可见）。
PORTAL.applyCapabilityVisibility = function() {
    var caps = PORTAL.capabilities();
    document.querySelectorAll('[data-capability]').forEach(function(el) {
        var need = el.getAttribute('data-capability');
        if (!need) return;
        // 一次可以声明多个能力，空格分隔，命中其一即显示
        var wanted = need.split(/\s+/).filter(Boolean);
        var ok = wanted.some(function(c) { return caps.indexOf(c) >= 0; });
        el.classList.toggle('is-hidden', !ok);
    });
};
