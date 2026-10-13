/* ============================================================
   粤乡智匠 — 消息中心（主站与后台管理页共用）
   ============================================================
   内容自 script.js 原样搬出，供 admin.html 复用（后台也要有消息中心）。
   依赖 js/core.js：AppState / apiCall / escapeHtml / STORAGE_KEYS。
   依赖宿主页面提供：#quick-message-btn、#msg-dropdown 及面板内部各 id，
   以及 showNotification / showDetailModal / bindLoginCta / openLoginModal
   （主站由 script.js 提供，后台由 admin.html 内联脚本提供）。
   暴露 window.MessageCenter 给宿主页面按需调用。
   ============================================================ */

// ==================== 消息通知 ====================

// 当前登录用户的真实 user_id（username）。严禁再用 AppState.currentUser（全站从未赋值，
// 会退化成 sessionId 这个 UUID，导致按 user_id 查不到任何数据 → 消息中心对谁都不可见）。
// 消息通知偏好：控制是否在消息中心接收「教师 / 企业 / 超级管理员」发布的系统公告。
// 关闭后消息中心不再拉取通知源、红点也不显示；用户可随时在设置中重新开启。
function isNotifEnabled() {
    try { return localStorage.getItem(STORAGE_KEYS.NOTIF) !== '0'; } catch (e) { return true; }
}

function setNotifEnabled(on) {
    try { localStorage.setItem(STORAGE_KEYS.NOTIF, on ? '1' : '0'); } catch (e) { /* 隐私模式忽略 */ }
}

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
        // 弹窗（通知详情 / 会话 / 登录等）打开期间，点弹窗内部不算「点击外部」——
        // 用户看完一条往往还要回来看其它消息，popover 该保持展开。
        if (e.target.closest && e.target.closest('.modal-overlay')) return;
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
            msgCenterTab = (tab === 'read') ? 'read' : (tab === 'unread' ? 'unread' : 'messages');
            document.getElementById('msg-notifications-list').classList.toggle('is-hidden', tab === 'messages');
            document.getElementById('msg-messages-list').classList.toggle('is-hidden', tab !== 'messages');
            // 未读 / 已读共用同一批数据，切换时重新过滤渲染即可
            if (tab !== 'messages') loadNotifications();
        });
    });

    // 头部红底未读按钮 → 跳到未读页签
    document.getElementById('msg-unread-jump')?.addEventListener('click', () => {
        msgCenterTab = 'unread';
        dropdown.querySelectorAll('.msg-tab-btn').forEach(b => {
            b.classList.toggle('active', b.dataset.tab === 'unread');
        });
        document.getElementById('msg-notifications-list').classList.remove('is-hidden');
        document.getElementById('msg-messages-list').classList.add('is-hidden');
        loadNotifications();
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
        // 一个接口数全四个数据源。此前是两个接口相加，只覆盖 notifications + messages，
        // 系统公告与投递状态永远不计入红点。
        const res = await apiCall(`/api/notifications/unread?user_id=${userId}`);
        const total = res.count || 0;
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

    // 已读旁路状态：系统公告与投递记录自身没有 is_read 字段，已读记录按用户存在
    // notification_reads 表里（后端 /api/notifications/read-state 下发）。
    // 没有这一步，「未读 / 已读」两个页签就只能覆盖 4 个数据源里的 2 个。
    let readRefs = { system_announcement: [], job_application: [] };
    try {
        const rs = await apiCall(`/api/notifications/read-state?user_id=${uid}`);
        if (rs && rs.success && rs.refs) readRefs = rs.refs;
    } catch (e) { console.warn('[消息中心] 已读状态加载失败', e); }
    const sysRead = new Set((readRefs.system_announcement || []).map(String));
    const jobRead = new Set((readRefs.job_application || []).map(String));

    const items = [];
    let srcFailed = 0;
    // 1. 管理员系统公告（只读）
    try {
        const r = await apiCall('/api/system-announcements');
        (r.announcements || []).forEach(a => items.push({
            key: 'sys:' + a.id, source: 'system_announcement', refId: String(a.id),
            type: 'announcement', tag: '系统公告', readOnly: true,
            isRead: sysRead.has(String(a.id)),
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
            key: 'job:' + a.id, source: 'job_application', refId: String(a.id),
            type: 'job', tag: '企业通知',
            replyId: a.enterprise_id || '', replyName: a.company || '企业',
            isRead: jobRead.has(String(a.id)),
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
                key: 'msg:' + (m.other_id || ''), source: 'messages', refId: String(m.other_id || ''),
                type: 'interaction', tag: '互动',
                replyId: m.other_id || '', replyName: m.other_name || '对方',
                isRead: !!m.is_read,
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
            key: 'notif:' + n.id, source: 'notifications', refId: String(n.id),
            type: n.type || 'system', tag: notifTagMap[n.type] || '通知', readOnly: true,
            isRead: !!n.is_read,
            title: n.title || '通知',
            preview: n.content || '',
            time: n.created_at || '',
            ts: new Date((n.created_at || '').replace(' ', 'T')).getTime() || 0
        }));
    } catch (e) { srcFailed++; console.warn('[消息中心] 站内通知加载失败', e); }

    renderUnreadCounters(items);

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

    // 未读 / 已读两个页签是同一批数据的两种过滤，不是两次请求
    const wantRead = (msgCenterTab === 'read');
    const shown = items.filter(it => !!it.isRead === wantRead);
    if (!shown.length) {
        container.innerHTML = wantRead
            ? '<div class="msg-empty"><i class="fas fa-envelope-open"></i><p>暂无已读通知</p></div>'
            : '<div class="msg-empty"><i class="fas fa-check-circle"></i><p>全部已读，没有待处理通知</p></div>';
        return;
    }
    shown.sort((a, b) => b.ts - a.ts);
    const iconMap = { announcement: 'fa-bullhorn', job: 'fa-briefcase', interaction: 'fa-comments',
                      grade: 'fa-check-circle', system: 'fa-bell' };
    container.innerHTML = shown.map(it => `
        <div class="msg-item ${it.replyId ? 'has-reply' : ''} ${it.isRead ? '' : 'unread'} is-clickable"
             role="button" tabindex="0"
             data-key="${escapeHtml(it.key)}" data-source="${escapeHtml(it.source)}"
             data-ref="${escapeHtml(it.refId)}"
             data-rid="${escapeHtml(it.replyId || '')}" data-rname="${escapeHtml(it.replyName || '')}"
             data-title="${escapeHtml(it.title)}"
             data-preview="${escapeHtml(it.preview)}"
             data-time="${escapeHtml(it.time)}"
             data-tag="${escapeHtml(it.tag)}">
            <div class="msg-item-icon type-${it.type}"><i class="fas ${iconMap[it.type] || 'fa-bell'}"></i></div>
            <div class="msg-item-text">
                <div class="msg-item-title">${escapeHtml(it.title)} <span class="msg-tag msg-tag-${it.type}">${it.tag}</span></div>
                <div class="msg-item-preview">${escapeHtml(it.preview)}</div>
                <div class="msg-item-time">${formatTimeAgo(it.time)}</div>
                ${it.replyId ? `<span class="msg-reply-btn" data-rid="${escapeHtml(it.replyId)}" data-rname="${escapeHtml(it.replyName || '')}">回复</span>` : ''}
            </div>
        </div>
    `).join('');

    // 整条可点（此前只有「回复」小按钮可点，盒子其他区域点了没反应）：
    // 有对话对象的（企业通知 / 互动）进会话窗口，没有的（系统公告 / 公告 / 实训批改）只做归档。
    container.querySelectorAll('.msg-item').forEach(el => {
        const open = () => handleNotificationItemClick(el);
        el.addEventListener('click', open);
        el.addEventListener('keydown', e => {
            if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(); }
        });
    });
}

// 当前停留在哪个页签：unread（未读）/ read（已读）/ messages（我的对话）
let msgCenterTab = 'unread';

// 未读/已读计数与两个入口（页签角标 + 头部红底按钮）的渲染
function renderUnreadCounters(items) {
    const unread = items.filter(it => !it.isRead).length;
    const jump = document.getElementById('msg-unread-jump');
    const jumpCount = document.getElementById('msg-unread-jump-count');
    if (jumpCount) jumpCount.textContent = unread;
    if (jump) jump.classList.toggle('is-hidden', unread === 0);
}

// 点击一条通知：未读的先归档（从未读列表消失、进已读），有对话对象的再跳会话窗口
async function handleNotificationItemClick(el) {
    const source = el.dataset.source;
    const ref = el.dataset.ref;
    const rid = el.dataset.rid;
    const wasUnread = el.classList.contains('unread');

    if (wasUnread && source && ref) {
        try {
            await apiCall('/api/notifications/read-one', 'POST',
                          { user_id: currentUserId(), source, ref_id: ref });
        } catch (e) { console.warn('[消息中心] 标记已读失败', e); }
    }
    if (rid) openConversation(rid, el.dataset.rname);

    // 没有对话对象的（系统公告 / 公告 / 实训批改）→ 弹详情弹窗看全文。
    // 列表里只有两行摘要，公告正文与批改评语都被截断了，点开才能看全。
    if (!rid) showNotificationDetail(el);

    if (wasUnread && msgCenterTab === 'unread') {
        el.remove();
        const list = document.getElementById('msg-notifications-list');
        if (list && !list.querySelector('.msg-item')) {
            list.innerHTML = '<div class="msg-empty"><i class="fas fa-check-circle"></i><p>全部已读，没有待处理通知</p></div>';
        }
    }
    updateBadgeCount();
}

// 通知详情弹窗：标题 + 类型标签 + 正文 + 时间
function showNotificationDetail(el) {
    const title = el.dataset.title || '通知';
    const tag = el.dataset.tag || '';
    const preview = el.dataset.preview || '';
    const time = el.dataset.time || '';
    const iconMap = { announcement: 'fa-bullhorn', job: 'fa-briefcase', interaction: 'fa-comments',
                      grade: 'fa-check-circle', system: 'fa-bell' };
    const type = el.querySelector('.msg-item-icon')?.className.match(/type-([\w-]+)/);
    const icon = (type && iconMap[type[1]]) || 'fa-bell';

    showDetailModal(title, `
        <div class="notif-detail">
            ${tag ? `<span class="msg-tag msg-tag-${type ? type[1] : 'system'}">${escapeHtml(tag)}</span>` : ''}
            <div class="notif-detail-body">${escapeHtml(preview) || '<p class="notif-detail-empty">暂无正文</p>'}</div>
            ${time ? `<div class="notif-detail-time"><i class="far fa-clock"></i> ${escapeHtml(time)}</div>` : ''}
        </div>
    `, icon);
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


// ==================== 对外接口 ====================
// 宿主页面在会话就绪后调用 MessageCenter.start()；登出时调用 stop()。
window.MessageCenter = {
    init: setupQuickMessage,
    start: function () {
        updateBadgeCount();
        startBadgePolling();
    },
    stop: function () {
        stopBadgePolling();
        stopConvPolling();
    },
    refreshBadge: updateBadgeCount
};
