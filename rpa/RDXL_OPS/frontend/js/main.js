/**
 * VibeOps Main JavaScript
 *
 * Multi-tenant dashboard with authentication and team context.
 */

document.addEventListener('DOMContentLoaded', async () => {
    // Check authentication
    if (!authManager.isAuthenticated()) {
        window.location.href = '/login.html';
        return;
    }

    // Initialize UI
    await initializeApp();
});

/**
 * Initialize the application
 */
async function initializeApp() {
    try {
        // Fetch fresh user data
        await authManager.fetchCurrentUser();
        const user = authManager.getUser();

        if (!user) {
            window.location.href = '/login.html';
            return;
        }

        // Update UI with user info
        updateUserUI(user);

        // Initialize components
        initNavigation();
        initUserMenu();
        initChat();
        initGuidelinesEditor();
        initPasswordForm();

        // Load dashboard
        await loadDashboard();

    } catch (error) {
        console.error('Initialization error:', error);
        showNotification('초기화 중 오류가 발생했습니다.', 'error');
    }
}

/**
 * Update UI with user information
 */
function updateUserUI(user) {
    // Header user info
    document.getElementById('user-avatar').textContent = user.name.charAt(0).toUpperCase();
    document.getElementById('user-name').textContent = user.name;
    document.getElementById('user-team').textContent = user.team_name || 'System Admin';

    // Sidebar team info
    document.getElementById('sidebar-team-name').textContent = user.team_name || 'System Admin';

    const roleBadge = document.getElementById('sidebar-role-badge');
    roleBadge.textContent = getRoleDisplayName(user.role);
    roleBadge.className = `role-badge role-${user.role}`;

    // Show/hide admin features
    const guidelinesBtn = document.getElementById('guidelines-btn');
    if (guidelinesBtn) {
        const isAdmin = user.role === 'super_admin' || user.role === 'team_admin';
        guidelinesBtn.classList.toggle('hidden', !isAdmin);
    }

    // Show/hide admin dashboard link
    const adminNavLink = document.getElementById('admin-nav-link');
    if (adminNavLink) {
        const isAdmin = user.role === 'super_admin' || user.role === 'team_admin';
        adminNavLink.classList.toggle('hidden', !isAdmin);
    }
}

/**
 * Get display name for role
 */
function getRoleDisplayName(role) {
    const roles = {
        'super_admin': '시스템 관리자',
        'team_admin': '팀 관리자',
        'member': '팀원'
    };
    return roles[role] || role;
}

/**
 * Initialize navigation with accessibility support
 */
function initNavigation() {
    const navItems = document.querySelectorAll('.nav-item[data-page]');
    const pages = document.querySelectorAll('.page');

    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();

            const targetPage = item.dataset.page;
            if (!targetPage) return;

            // Update active nav item and aria-current
            navItems.forEach(nav => {
                nav.classList.remove('active');
                nav.removeAttribute('aria-current');
            });
            item.classList.add('active');
            item.setAttribute('aria-current', 'page');

            // Show target page
            pages.forEach(page => {
                const isActive = page.id === `page-${targetPage}`;
                page.classList.toggle('active', isActive);
                page.setAttribute('aria-hidden', !isActive);
            });

            // Announce page change for screen readers
            announcePageChange(targetPage);

            // Load page-specific content
            if (targetPage === 'knowledge') {
                loadKnowledgePage();
            } else if (targetPage === 'settings') {
                loadSettingsPage();
            }
        });

        // Keyboard navigation
        item.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                item.click();
            }
        });
    });
}

/**
 * Announce page change for screen readers
 */
function announcePageChange(pageName) {
    const pageNames = {
        dashboard: '대시보드',
        chat: 'AI 채팅',
        agents: '에이전트',
        knowledge: '지식베이스',
        settings: '설정'
    };

    const announcement = `${pageNames[pageName] || pageName} 페이지로 이동했습니다.`;

    // Create or update live region
    let liveRegion = document.getElementById('page-announcement');
    if (!liveRegion) {
        liveRegion = document.createElement('div');
        liveRegion.id = 'page-announcement';
        liveRegion.className = 'sr-only';
        liveRegion.setAttribute('aria-live', 'polite');
        liveRegion.setAttribute('aria-atomic', 'true');
        document.body.appendChild(liveRegion);
    }

    liveRegion.textContent = announcement;
}

/**
 * Initialize user menu with keyboard navigation support
 */
function initUserMenu() {
    const userBtn = document.getElementById('user-btn');
    const dropdown = document.getElementById('user-dropdown');
    const logoutBtn = document.getElementById('logout-btn');
    const menuItems = dropdown.querySelectorAll('[role="menuitem"]');

    // Toggle dropdown
    function toggleDropdown(show) {
        const isVisible = show !== undefined ? show : !dropdown.classList.contains('visible');
        dropdown.classList.toggle('visible', isVisible);
        userBtn.setAttribute('aria-expanded', isVisible);

        if (isVisible && menuItems.length > 0) {
            // Focus first menu item when opening
            menuItems[0].focus();
            menuItems[0].setAttribute('tabindex', '0');
        } else {
            // Reset tabindex when closing
            menuItems.forEach(item => item.setAttribute('tabindex', '-1'));
        }
    }

    // Click handler
    userBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        toggleDropdown();
    });

    // Keyboard navigation for user button
    userBtn.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ' || e.key === 'ArrowDown') {
            e.preventDefault();
            toggleDropdown(true);
        }
    });

    // Keyboard navigation within dropdown
    dropdown.addEventListener('keydown', (e) => {
        const currentIndex = Array.from(menuItems).indexOf(document.activeElement);

        switch (e.key) {
            case 'ArrowDown':
                e.preventDefault();
                if (currentIndex < menuItems.length - 1) {
                    menuItems[currentIndex + 1].focus();
                }
                break;
            case 'ArrowUp':
                e.preventDefault();
                if (currentIndex > 0) {
                    menuItems[currentIndex - 1].focus();
                }
                break;
            case 'Escape':
                e.preventDefault();
                toggleDropdown(false);
                userBtn.focus();
                break;
            case 'Tab':
                // Close dropdown when tabbing out
                toggleDropdown(false);
                break;
        }
    });

    // Close dropdown on outside click
    document.addEventListener('click', () => {
        toggleDropdown(false);
    });

    // Logout
    logoutBtn.addEventListener('click', async (e) => {
        e.preventDefault();
        await authManager.logout();
        window.location.href = '/login.html';
    });
}

/**
 * Initialize chat functionality with WebSocket bridge
 */
function initChat() {
    const form = document.getElementById('chat-form');
    const input = document.getElementById('chat-input');
    const messages = document.getElementById('chat-messages');
    let currentTypingId = null;

    // Connect to WebSocket bridge
    connectBridge();

    // Handle form submission
    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const text = input.value.trim();
        if (!text) return;

        // Check connection
        if (!bridgeClient.isConnected()) {
            addMessage('브릿지에 연결되어 있지 않습니다. 재연결 중...', 'system');
            await connectBridge();
            if (!bridgeClient.isConnected()) {
                addMessage('브릿지 연결 실패. 페이지를 새로고침 해주세요.', 'system');
                return;
            }
        }

        // Add user message
        addMessage(text, 'user');
        input.value = '';

        // Show typing indicator
        currentTypingId = showTyping();

        // Send command via WebSocket
        bridgeClient.sendCommand(text);
    });

    async function connectBridge() {
        try {
            // Set up message handlers
            bridgeClient.on('status', (payload) => {
                console.log('Bridge status:', payload);
                if (payload.status === 'connected') {
                    updateConnectionStatus(true);
                }
            });

            bridgeClient.on('stream', (payload) => {
                // Update typing indicator with progress
                if (currentTypingId) {
                    const el = document.getElementById(currentTypingId);
                    if (el) {
                        el.textContent = payload.message || '처리 중...';
                    }
                }
            });

            bridgeClient.on('response', (payload) => {
                // Remove typing indicator
                if (currentTypingId) {
                    removeTyping(currentTypingId);
                    currentTypingId = null;
                }
                // Add AI response
                addMessage(payload.result || payload.message || '응답을 받지 못했습니다.', 'assistant');
            });

            bridgeClient.on('error', (payload) => {
                if (currentTypingId) {
                    removeTyping(currentTypingId);
                    currentTypingId = null;
                }
                addMessage('오류: ' + (payload.message || '알 수 없는 오류'), 'system');
            });

            bridgeClient.on('disconnected', () => {
                updateConnectionStatus(false);
            });

            // Connect
            await bridgeClient.connect();
            console.log('Bridge connected successfully');

        } catch (error) {
            console.error('Bridge connection failed:', error);
            updateConnectionStatus(false);
        }
    }

    function addMessage(text, type) {
        const welcome = messages.querySelector('.chat-welcome');
        if (welcome) welcome.remove();

        const msg = document.createElement('div');
        msg.className = `chat-message ${type}`;
        // Support multi-line text with proper formatting
        msg.style.whiteSpace = 'pre-wrap';
        msg.textContent = text;
        messages.appendChild(msg);
        messages.scrollTop = messages.scrollHeight;
    }

    function showTyping() {
        const id = 'typing-' + Date.now();
        const msg = document.createElement('div');
        msg.id = id;
        msg.className = 'chat-message assistant';
        msg.textContent = '처리 중...';
        msg.style.opacity = '0.7';
        messages.appendChild(msg);
        messages.scrollTop = messages.scrollHeight;
        return id;
    }

    function removeTyping(id) {
        const el = document.getElementById(id);
        if (el) el.remove();
    }
}

/**
 * Initialize guidelines editor
 */
function initGuidelinesEditor() {
    const guidelinesBtn = document.getElementById('guidelines-btn');
    const editor = document.getElementById('team-guidelines-editor');
    const textarea = document.getElementById('team-guidelines-textarea');
    const saveBtn = document.getElementById('save-guidelines-btn');
    const cancelBtn = document.getElementById('cancel-guidelines-btn');

    let originalContent = '';

    guidelinesBtn?.addEventListener('click', async (e) => {
        e.preventDefault();

        // Navigate to knowledge page
        document.querySelector('.nav-item[data-page="knowledge"]').click();

        // Load and show editor
        await loadKnowledgePage();
        editor.classList.add('visible');
    });

    saveBtn?.addEventListener('click', async () => {
        const user = authManager.getUser();
        if (!user.team_name && user.role !== 'super_admin') {
            showNotification('팀에 소속되어 있지 않습니다.', 'error');
            return;
        }

        // For super_admin without team, skip
        const teamSlug = getTeamSlug();
        if (!teamSlug) {
            showNotification('팀 지침을 편집할 수 없습니다.', 'error');
            return;
        }

        try {
            const response = await authManager.apiRequest(`/api/knowledge/team/${teamSlug}/guideline`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(textarea.value)
            });

            if (response.ok) {
                showNotification('지침이 저장되었습니다.', 'success');
                editor.classList.remove('visible');
                await loadKnowledgePage();
            } else {
                const error = await response.json();
                throw new Error(error.detail || 'Save failed');
            }
        } catch (error) {
            showNotification('저장 실패: ' + error.message, 'error');
        }
    });

    cancelBtn?.addEventListener('click', () => {
        textarea.value = originalContent;
        editor.classList.remove('visible');
    });
}

/**
 * Initialize password form
 */
function initPasswordForm() {
    const form = document.getElementById('password-form');

    form?.addEventListener('submit', async (e) => {
        e.preventDefault();

        const currentPassword = document.getElementById('current-password').value;
        const newPassword = document.getElementById('new-password').value;

        try {
            const response = await authManager.apiRequest('/api/auth/change-password', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    current_password: currentPassword,
                    new_password: newPassword
                })
            });

            if (response.ok) {
                showNotification('비밀번호가 변경되었습니다.', 'success');
                form.reset();
            } else {
                const error = await response.json();
                throw new Error(error.detail || 'Password change failed');
            }
        } catch (error) {
            showNotification('비밀번호 변경 실패: ' + error.message, 'error');
        }
    });
}

/**
 * Load dashboard data
 */
async function loadDashboard() {
    const systemStatus = document.getElementById('system-status');
    const teamInfo = document.getElementById('team-info-detail');

    try {
        // Fetch health status
        const healthResponse = await fetch('/health');
        const health = await healthResponse.json();

        systemStatus.innerHTML = `
            <p><strong>상태:</strong> ${health.status}</p>
            <p><strong>시간:</strong> ${new Date(health.timestamp).toLocaleString()}</p>
        `;

        updateConnectionStatus(true);

        // Fetch team context
        const user = authManager.getUser();
        const teamSlug = getTeamSlug();

        if (teamSlug) {
            const contextResponse = await authManager.apiRequest(`/api/knowledge/context/${teamSlug}`);
            if (contextResponse.ok) {
                const context = await contextResponse.json();
                teamInfo.innerHTML = `
                    <p><strong>팀:</strong> ${context.team_name}</p>
                    <p><strong>Slug:</strong> ${context.team_slug}</p>
                    <p><strong>권한:</strong> ${getRoleDisplayName(user.role)}</p>
                    <p><strong>Master 지식 파일:</strong> ${context.master_knowledge_files?.length || 0}개</p>
                    <p><strong>팀 지식 파일:</strong> ${context.team_knowledge_files?.length || 0}개</p>
                `;
            }
        } else {
            teamInfo.innerHTML = `
                <p><strong>역할:</strong> ${getRoleDisplayName(user.role)}</p>
                <p>시스템 관리자는 모든 팀에 접근할 수 있습니다.</p>
            `;
        }

    } catch (error) {
        systemStatus.innerHTML = `
            <p class="error">서버에 연결할 수 없습니다.</p>
            <p class="hint">서버가 실행 중인지 확인해주세요.</p>
        `;

        updateConnectionStatus(false);
    }
}

/**
 * Load knowledge page content
 */
async function loadKnowledgePage() {
    const masterPreview = document.getElementById('master-guideline-preview');
    const teamPreview = document.getElementById('team-guideline-preview');
    const textarea = document.getElementById('team-guidelines-textarea');
    const user = authManager.getUser();

    try {
        // Load master guideline
        const masterResponse = await authManager.apiRequest('/api/knowledge/master/guideline');
        if (masterResponse.ok) {
            const master = await masterResponse.json();
            masterPreview.innerHTML = `
                <pre style="white-space: pre-wrap; font-size: 0.85rem; max-height: 200px; overflow: auto;">${escapeHtml(master.content.substring(0, 1000))}${master.content.length > 1000 ? '\n...' : ''}</pre>
            `;
        }

        // Load team guideline
        const teamSlug = getTeamSlug();
        if (teamSlug) {
            const teamResponse = await authManager.apiRequest(`/api/knowledge/team/${teamSlug}/guideline`);
            if (teamResponse.ok) {
                const team = await teamResponse.json();
                teamPreview.innerHTML = `
                    <pre style="white-space: pre-wrap; font-size: 0.85rem; max-height: 200px; overflow: auto;">${escapeHtml(team.content || '(내용 없음)')}</pre>
                    ${team.can_edit ? '<button class="btn btn-secondary" id="edit-team-guidelines">편집</button>' : ''}
                `;
                textarea.value = team.content || '';

                // Bind edit button
                document.getElementById('edit-team-guidelines')?.addEventListener('click', () => {
                    document.getElementById('team-guidelines-editor').classList.add('visible');
                });
            }
        } else {
            teamPreview.innerHTML = `<p class="text-muted">시스템 관리자는 특정 팀의 지침을 조회하려면 팀을 선택해주세요.</p>`;
        }

    } catch (error) {
        console.error('Knowledge load error:', error);
    }
}

/**
 * Load settings page content
 */
function loadSettingsPage() {
    const accountInfo = document.getElementById('account-info');
    const user = authManager.getUser();

    accountInfo.innerHTML = `
        <p><strong>이름:</strong> ${user.name}</p>
        <p><strong>이메일:</strong> ${user.email}</p>
        <p><strong>역할:</strong> ${getRoleDisplayName(user.role)}</p>
        <p><strong>팀:</strong> ${user.team_name || '-'}</p>
        <p><strong>마지막 로그인:</strong> ${user.last_login ? new Date(user.last_login).toLocaleString() : '-'}</p>
    `;
}

/**
 * Get team slug from user info
 */
function getTeamSlug() {
    const user = authManager.getUser();
    if (!user) return null;

    // Map team names to slugs
    const teamSlugs = {
        '경영기획팀': 'management',
        '로보틱스팀': 'robotics',
        'SW팀': 'software',
        '기술전략팀': 'strategy',
        'RA/QA팀': 'raqa'
    };

    return teamSlugs[user.team_name] || null;
}

/**
 * Update connection status indicator
 */
function updateConnectionStatus(connected) {
    const badge = document.getElementById('connection-status');

    if (connected) {
        badge.className = 'status-badge status-connected';
        badge.textContent = '연결됨';
    } else {
        badge.className = 'status-badge status-disconnected';
        badge.textContent = '연결 안됨';
    }
}

/**
 * Show notification using Toast system
 */
function showNotification(message, type = 'info') {
    // Use ToastManager if available, fallback to console
    if (typeof ToastManager !== 'undefined') {
        return ToastManager.show(message, { type });
    }
    console.log(`[${type.toUpperCase()}] ${message}`);
}

/**
 * Escape HTML
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
