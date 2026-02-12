/**
 * VibeOps Admin Dashboard JavaScript
 *
 * Handles admin functionality: user management, feedback, and Claude Bridge.
 */

document.addEventListener('DOMContentLoaded', async () => {
    // Check authentication
    if (!authManager.isAuthenticated()) {
        window.location.href = '/login.html';
        return;
    }

    // Check admin permission
    const user = authManager.getUser();
    if (user && user.role !== 'super_admin' && user.role !== 'team_admin') {
        window.location.href = '/index.html';
        return;
    }

    // Initialize admin dashboard
    await initializeAdmin();
});

/**
 * Global state
 */
const adminState = {
    users: [],
    pendingUsers: [],
    feedback: [],
    teams: [],
    agents: [],
    schedules: [],
    currentPage: 1,
    pageSize: 10,
    sortField: 'name',
    sortOrder: 'asc',
    filters: {
        search: '',
        role: '',
        status: '',
        team: ''
    },
    selectedFeedback: new Set(),
    agentRunning: new Set()
};

/**
 * Initialize admin dashboard
 */
async function initializeAdmin() {
    try {
        // Update user info
        const user = authManager.getUser();
        document.getElementById('admin-avatar').textContent = user.name.charAt(0).toUpperCase();
        document.getElementById('admin-name').textContent = user.name;

        // Initialize components
        initTabs();
        initUserManagement();
        initFeedback();
        initBridge();
        initAgents();
        initSchedules();

        // Load initial data
        await Promise.all([
            loadTeams(),
            loadPendingUsers(),
            loadUsers(),
            loadFeedback()
        ]);

    } catch (error) {
        console.error('Admin initialization error:', error);
        showToast('초기화 중 오류가 발생했습니다.', 'error');
    }
}

/**
 * Initialize tab navigation
 */
function initTabs() {
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabPanes = document.querySelectorAll('.tab-pane');

    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetTab = btn.dataset.tab;

            // Update active states
            tabBtns.forEach(b => b.classList.remove('active'));
            tabPanes.forEach(p => p.classList.remove('active'));

            btn.classList.add('active');
            document.getElementById(`tab-${targetTab}`).classList.add('active');

            // Tab-specific actions
            if (targetTab === 'bridge') {
                connectBridge();
            } else if (targetTab === 'agents') {
                loadAgents();
            } else if (targetTab === 'schedules') {
                loadSchedules();
            }
        });
    });
}

/**
 * Load teams for filters and selects
 */
async function loadTeams() {
    try {
        const response = await authManager.apiRequest('/api/admin/teams');
        if (response.ok) {
            adminState.teams = await response.json();
            populateTeamSelects();
        }
    } catch (error) {
        console.error('Failed to load teams:', error);
    }
}

/**
 * Populate team select elements
 */
function populateTeamSelects() {
    const teamFilter = document.getElementById('team-filter');
    const editTeamSelect = document.getElementById('edit-user-team');

    const options = adminState.teams.map(team =>
        `<option value="${team.id}">${team.name}</option>`
    ).join('');

    if (teamFilter) {
        teamFilter.innerHTML = '<option value="">모든 팀</option>' + options;
    }

    if (editTeamSelect) {
        editTeamSelect.innerHTML = '<option value="">팀 없음</option>' + options;
    }
}

// ==================== PENDING USERS ====================

/**
 * Load pending users
 */
async function loadPendingUsers() {
    try {
        const response = await authManager.apiRequest('/api/admin/users/pending');
        if (response.ok) {
            adminState.pendingUsers = await response.json();
            renderPendingUsers();
            updatePendingCount();
        }
    } catch (error) {
        console.error('Failed to load pending users:', error);
    }
}

/**
 * Render pending users list
 */
function renderPendingUsers() {
    const container = document.getElementById('pending-list');

    if (adminState.pendingUsers.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <svg class="empty-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                    <path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
                </svg>
                <p>승인 대기 중인 사용자가 없습니다.</p>
            </div>
        `;
        return;
    }

    container.innerHTML = adminState.pendingUsers.map(user => `
        <div class="pending-card" data-id="${user.id}">
            <div class="pending-user-info">
                <div class="pending-avatar">${user.name.charAt(0).toUpperCase()}</div>
                <div class="pending-details">
                    <h4>${escapeHtml(user.email)}</h4>
                    <p>${escapeHtml(user.name)} ${user.company ? '· ' + escapeHtml(user.company) : ''} · ${formatDate(user.created_at)}</p>
                </div>
            </div>
            <div class="pending-actions">
                <button class="btn btn-success btn-sm" onclick="approveUser(${user.id})">승인</button>
                <button class="btn btn-danger btn-sm" onclick="rejectUser(${user.id})">거절</button>
            </div>
        </div>
    `).join('');
}

/**
 * Update pending count badge
 */
function updatePendingCount() {
    const badge = document.getElementById('pending-count');
    badge.textContent = adminState.pendingUsers.length;
    badge.style.display = adminState.pendingUsers.length > 0 ? 'inline' : 'none';
}

/**
 * Approve user
 */
async function approveUser(userId) {
    try {
        const response = await authManager.apiRequest(`/api/admin/users/${userId}/approve`, {
            method: 'POST'
        });

        if (response.ok) {
            showToast('사용자가 승인되었습니다.', 'success');
            await loadPendingUsers();
            await loadUsers();
        } else {
            throw new Error('Approval failed');
        }
    } catch (error) {
        showToast('승인 처리 중 오류가 발생했습니다.', 'error');
    }
}

/**
 * Reject user
 */
async function rejectUser(userId) {
    if (!confirm('정말 이 사용자를 거절하시겠습니까?')) {
        return;
    }

    try {
        const response = await authManager.apiRequest(`/api/admin/users/${userId}/reject`, {
            method: 'POST'
        });

        if (response.ok) {
            showToast('사용자가 거절되었습니다.', 'success');
            await loadPendingUsers();
        } else {
            throw new Error('Rejection failed');
        }
    } catch (error) {
        showToast('거절 처리 중 오류가 발생했습니다.', 'error');
    }
}

// ==================== USER MANAGEMENT ====================

/**
 * Initialize user management
 */
function initUserManagement() {
    // Search
    const searchInput = document.getElementById('user-search');
    let searchTimeout;
    searchInput.addEventListener('input', (e) => {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
            adminState.filters.search = e.target.value;
            adminState.currentPage = 1;
            loadUsers();
        }, 300);
    });

    // Filters
    ['role', 'status', 'team'].forEach(filter => {
        document.getElementById(`${filter}-filter`).addEventListener('change', (e) => {
            adminState.filters[filter] = e.target.value;
            adminState.currentPage = 1;
            loadUsers();
        });
    });

    // Sorting
    document.querySelectorAll('.sortable').forEach(th => {
        th.addEventListener('click', () => {
            const field = th.dataset.sort;
            if (adminState.sortField === field) {
                adminState.sortOrder = adminState.sortOrder === 'asc' ? 'desc' : 'asc';
            } else {
                adminState.sortField = field;
                adminState.sortOrder = 'asc';
            }
            loadUsers();
        });
    });

    // Modal handlers
    document.getElementById('close-user-modal').addEventListener('click', closeUserModal);
    document.getElementById('cancel-user-edit').addEventListener('click', closeUserModal);
    document.getElementById('save-user-edit').addEventListener('click', saveUserEdit);

    // Close modal on overlay click
    document.getElementById('user-edit-modal').addEventListener('click', (e) => {
        if (e.target.classList.contains('modal-overlay')) {
            closeUserModal();
        }
    });
}

/**
 * Load users
 */
async function loadUsers() {
    try {
        const params = new URLSearchParams({
            page: adminState.currentPage,
            limit: adminState.pageSize,
            sort: adminState.sortField,
            order: adminState.sortOrder
        });

        if (adminState.filters.search) params.append('search', adminState.filters.search);
        if (adminState.filters.role) params.append('role', adminState.filters.role);
        if (adminState.filters.status) params.append('status', adminState.filters.status);
        if (adminState.filters.team) params.append('team_id', adminState.filters.team);

        const response = await authManager.apiRequest(`/api/admin/users?${params}`);
        if (response.ok) {
            const data = await response.json();
            adminState.users = data.users;
            renderUsersTable();
            renderPagination(data.total);
        }
    } catch (error) {
        console.error('Failed to load users:', error);
    }
}

/**
 * Render users table
 */
function renderUsersTable() {
    const tbody = document.getElementById('users-table-body');

    if (adminState.users.length === 0) {
        tbody.innerHTML = `
            <tr class="loading-row">
                <td colspan="7">검색 결과가 없습니다.</td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = adminState.users.map(user => `
        <tr>
            <td>
                <div class="user-cell">
                    <div class="user-table-avatar">${user.name.charAt(0).toUpperCase()}</div>
                    <span>${escapeHtml(user.name)}</span>
                </div>
            </td>
            <td>${escapeHtml(user.email)}</td>
            <td>${user.team_name || '-'}</td>
            <td><span class="role-tag role-${user.role}">${getRoleName(user.role)}</span></td>
            <td>
                <span class="status-tag ${user.is_active ? 'status-active' : 'status-inactive'}">
                    <span class="status-dot"></span>
                    ${user.is_active ? '활성' : '비활성'}
                </span>
            </td>
            <td>${user.last_login ? formatDate(user.last_login) : '-'}</td>
            <td>
                <button class="action-btn" onclick="editUser(${user.id})" title="편집">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/>
                        <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/>
                    </svg>
                </button>
            </td>
        </tr>
    `).join('');
}

/**
 * Render pagination
 */
function renderPagination(total) {
    const container = document.getElementById('users-pagination');
    const totalPages = Math.ceil(total / adminState.pageSize);

    if (totalPages <= 1) {
        container.innerHTML = '';
        return;
    }

    let html = `
        <button class="page-btn" onclick="goToPage(${adminState.currentPage - 1})" ${adminState.currentPage === 1 ? 'disabled' : ''}>
            이전
        </button>
    `;

    for (let i = 1; i <= totalPages; i++) {
        if (i === 1 || i === totalPages || (i >= adminState.currentPage - 2 && i <= adminState.currentPage + 2)) {
            html += `
                <button class="page-btn ${i === adminState.currentPage ? 'active' : ''}" onclick="goToPage(${i})">
                    ${i}
                </button>
            `;
        } else if (i === adminState.currentPage - 3 || i === adminState.currentPage + 3) {
            html += '<span>...</span>';
        }
    }

    html += `
        <button class="page-btn" onclick="goToPage(${adminState.currentPage + 1})" ${adminState.currentPage === totalPages ? 'disabled' : ''}>
            다음
        </button>
    `;

    container.innerHTML = html;
}

/**
 * Go to page
 */
function goToPage(page) {
    adminState.currentPage = page;
    loadUsers();
}

/**
 * Edit user
 */
function editUser(userId) {
    const user = adminState.users.find(u => u.id === userId);
    if (!user) return;

    document.getElementById('edit-user-id').value = user.id;
    document.getElementById('edit-user-name').value = user.name;
    document.getElementById('edit-user-email').value = user.email;
    document.getElementById('edit-user-team').value = user.team_id || '';
    document.getElementById('edit-user-role').value = user.role;
    document.getElementById('edit-user-active').checked = user.is_active;

    document.getElementById('user-edit-modal').classList.add('visible');
}

/**
 * Close user modal
 */
function closeUserModal() {
    document.getElementById('user-edit-modal').classList.remove('visible');
}

/**
 * Save user edit
 */
async function saveUserEdit() {
    const userId = document.getElementById('edit-user-id').value;
    const data = {
        name: document.getElementById('edit-user-name').value,
        team_id: document.getElementById('edit-user-team').value || null,
        role: document.getElementById('edit-user-role').value,
        is_active: document.getElementById('edit-user-active').checked
    };

    try {
        const response = await authManager.apiRequest(`/api/admin/users/${userId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });

        if (response.ok) {
            showToast('사용자 정보가 업데이트되었습니다.', 'success');
            closeUserModal();
            await loadUsers();
        } else {
            throw new Error('Update failed');
        }
    } catch (error) {
        showToast('업데이트 중 오류가 발생했습니다.', 'error');
    }
}

// ==================== FEEDBACK ====================

/**
 * Initialize feedback
 */
function initFeedback() {
    // Status filter
    document.getElementById('feedback-status-filter').addEventListener('change', (e) => {
        loadFeedback(e.target.value);
    });

    // Bulk action button
    document.getElementById('bulk-action-btn').addEventListener('click', showBulkActions);

    // Modal handlers
    document.getElementById('close-feedback-modal').addEventListener('click', closeFeedbackModal);
    document.getElementById('close-feedback-detail').addEventListener('click', closeFeedbackModal);
    document.getElementById('send-to-bridge').addEventListener('click', sendFeedbackToBridge);

    // Close modal on overlay click
    document.getElementById('feedback-detail-modal').addEventListener('click', (e) => {
        if (e.target.classList.contains('modal-overlay')) {
            closeFeedbackModal();
        }
    });
}

/**
 * Load feedback
 */
async function loadFeedback(status = '') {
    try {
        const params = status ? `?status=${status}` : '';
        const response = await authManager.apiRequest(`/api/admin/feedback${params}`);
        if (response.ok) {
            adminState.feedback = await response.json();
            renderFeedbackList();
            updateFeedbackCount();
        }
    } catch (error) {
        console.error('Failed to load feedback:', error);
    }
}

/**
 * Render feedback list
 */
function renderFeedbackList() {
    const container = document.getElementById('feedback-list');

    if (adminState.feedback.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <svg class="empty-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                    <path d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/>
                </svg>
                <p>피드백이 없습니다.</p>
            </div>
        `;
        return;
    }

    container.innerHTML = adminState.feedback.map(fb => `
        <div class="feedback-item" data-id="${fb.id}">
            <div class="feedback-header" onclick="toggleFeedback(${fb.id})">
                <div class="feedback-header-left">
                    <input type="checkbox" class="feedback-checkbox" onclick="event.stopPropagation(); toggleFeedbackSelect(${fb.id}, this.checked)">
                    <span class="feedback-status ${fb.status}">${getStatusName(fb.status)}</span>
                    <span class="feedback-title">"${escapeHtml(fb.title || fb.content.substring(0, 50))}..."</span>
                </div>
                <div style="display: flex; align-items: center; gap: 1rem;">
                    <span class="feedback-meta">${escapeHtml(fb.user_email)} · ${formatDate(fb.created_at)}</span>
                    <svg class="feedback-expand-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M6 9l6 6 6-6"/>
                    </svg>
                </div>
            </div>
            <div class="feedback-body">
                <div class="feedback-content">${escapeHtml(fb.content)}</div>
                <div class="feedback-actions">
                    <select class="filter-select" onchange="updateFeedbackStatus(${fb.id}, this.value)">
                        <option value="new" ${fb.status === 'new' ? 'selected' : ''}>신규</option>
                        <option value="reviewing" ${fb.status === 'reviewing' ? 'selected' : ''}>검토중</option>
                        <option value="resolved" ${fb.status === 'resolved' ? 'selected' : ''}>해결됨</option>
                    </select>
                    <button class="btn btn-primary btn-sm" onclick="openFeedbackDetail(${fb.id})">상세보기</button>
                    <button class="btn btn-secondary btn-sm" onclick="sendSingleFeedbackToBridge(${fb.id})">브릿지로 전송</button>
                    <button class="btn btn-danger btn-sm" onclick="deleteFeedback(${fb.id})">삭제</button>
                </div>
            </div>
        </div>
    `).join('');
}

/**
 * Update feedback count badge
 */
function updateFeedbackCount() {
    const badge = document.getElementById('feedback-count');
    const newCount = adminState.feedback.filter(fb => fb.status === 'new').length;
    badge.textContent = newCount;
    badge.style.display = newCount > 0 ? 'inline' : 'none';
}

/**
 * Toggle feedback expand
 */
function toggleFeedback(id) {
    const item = document.querySelector(`.feedback-item[data-id="${id}"]`);
    item.classList.toggle('expanded');
}

/**
 * Toggle feedback selection
 */
function toggleFeedbackSelect(id, checked) {
    if (checked) {
        adminState.selectedFeedback.add(id);
    } else {
        adminState.selectedFeedback.delete(id);
    }

    document.getElementById('bulk-action-btn').disabled = adminState.selectedFeedback.size === 0;
}

/**
 * Show bulk actions
 */
function showBulkActions() {
    const actions = ['검토중으로 변경', '해결됨으로 변경', '선택 삭제'];
    const action = prompt(`선택된 ${adminState.selectedFeedback.size}개 피드백에 대해 수행할 작업을 선택하세요:\n1. 검토중으로 변경\n2. 해결됨으로 변경\n3. 선택 삭제\n\n번호를 입력하세요:`);

    if (action === '1') {
        bulkUpdateStatus('reviewing');
    } else if (action === '2') {
        bulkUpdateStatus('resolved');
    } else if (action === '3') {
        bulkDelete();
    }
}

/**
 * Bulk update feedback status
 */
async function bulkUpdateStatus(status) {
    try {
        const promises = Array.from(adminState.selectedFeedback).map(id =>
            authManager.apiRequest(`/api/admin/feedback/${id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ status })
            })
        );

        await Promise.all(promises);
        showToast('상태가 업데이트되었습니다.', 'success');
        adminState.selectedFeedback.clear();
        await loadFeedback();
    } catch (error) {
        showToast('업데이트 중 오류가 발생했습니다.', 'error');
    }
}

/**
 * Bulk delete feedback
 */
async function bulkDelete() {
    if (!confirm(`선택된 ${adminState.selectedFeedback.size}개의 피드백을 삭제하시겠습니까?`)) {
        return;
    }

    try {
        const promises = Array.from(adminState.selectedFeedback).map(id =>
            authManager.apiRequest(`/api/admin/feedback/${id}`, { method: 'DELETE' })
        );

        await Promise.all(promises);
        showToast('삭제되었습니다.', 'success');
        adminState.selectedFeedback.clear();
        await loadFeedback();
    } catch (error) {
        showToast('삭제 중 오류가 발생했습니다.', 'error');
    }
}

/**
 * Update single feedback status
 */
async function updateFeedbackStatus(id, status) {
    try {
        const response = await authManager.apiRequest(`/api/admin/feedback/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status })
        });

        if (response.ok) {
            showToast('상태가 업데이트되었습니다.', 'success');
            await loadFeedback();
        }
    } catch (error) {
        showToast('업데이트 중 오류가 발생했습니다.', 'error');
    }
}

/**
 * Delete single feedback
 */
async function deleteFeedback(id) {
    if (!confirm('이 피드백을 삭제하시겠습니까?')) {
        return;
    }

    try {
        const response = await authManager.apiRequest(`/api/admin/feedback/${id}`, {
            method: 'DELETE'
        });

        if (response.ok) {
            showToast('삭제되었습니다.', 'success');
            await loadFeedback();
        }
    } catch (error) {
        showToast('삭제 중 오류가 발생했습니다.', 'error');
    }
}

/**
 * Open feedback detail modal
 * Uses DOM API instead of innerHTML for XSS prevention
 */
function openFeedbackDetail(id) {
    const fb = adminState.feedback.find(f => f.id === id);
    if (!fb) return;

    const body = document.getElementById('feedback-detail-body');
    body.innerHTML = ''; // Clear existing content

    // Create feedback detail container
    const detail = document.createElement('div');
    detail.className = 'feedback-detail';

    // Helper function to create info items safely
    const createInfoItem = (label, value, isHtml = false) => {
        const item = document.createElement('div');
        item.className = 'info-item';

        const labelSpan = document.createElement('span');
        labelSpan.className = 'info-label';
        labelSpan.textContent = label;

        const valueSpan = document.createElement('span');
        valueSpan.className = 'info-value';
        if (isHtml) {
            valueSpan.appendChild(value);
        } else {
            valueSpan.textContent = value;
        }

        item.appendChild(labelSpan);
        item.appendChild(valueSpan);
        return item;
    };

    // Submitter info
    detail.appendChild(createInfoItem('제출자', fb.user_email));

    // Status badge
    const statusBadge = document.createElement('span');
    statusBadge.className = `feedback-status ${fb.status}`;
    statusBadge.textContent = getStatusName(fb.status);
    detail.appendChild(createInfoItem('상태', statusBadge, true));

    // Date
    detail.appendChild(createInfoItem('제출일', formatDate(fb.created_at)));

    // Content section
    const contentSection = document.createElement('div');
    contentSection.style.marginTop = '1rem';

    const contentLabel = document.createElement('label');
    contentLabel.style.fontWeight = '500';
    contentLabel.style.marginBottom = '0.5rem';
    contentLabel.style.display = 'block';
    contentLabel.textContent = '내용';

    const contentDiv = document.createElement('div');
    contentDiv.className = 'feedback-content';
    contentDiv.textContent = fb.content;  // textContent is XSS-safe
    contentDiv.style.whiteSpace = 'pre-wrap';

    contentSection.appendChild(contentLabel);
    contentSection.appendChild(contentDiv);
    detail.appendChild(contentSection);

    body.appendChild(detail);

    document.getElementById('send-to-bridge').dataset.feedbackId = id;
    document.getElementById('feedback-detail-modal').classList.add('visible');
}

/**
 * Close feedback modal
 */
function closeFeedbackModal() {
    document.getElementById('feedback-detail-modal').classList.remove('visible');
}

/**
 * Send feedback to bridge
 */
function sendFeedbackToBridge() {
    const id = document.getElementById('send-to-bridge').dataset.feedbackId;
    sendSingleFeedbackToBridge(id);
    closeFeedbackModal();
}

/**
 * Send single feedback to bridge
 */
function sendSingleFeedbackToBridge(id) {
    const fb = adminState.feedback.find(f => f.id === id);
    if (!fb) return;

    // Switch to bridge tab
    document.querySelector('.tab-btn[data-tab="bridge"]').click();

    // Set the input and submit
    const input = document.getElementById('bridge-input');
    input.value = `[피드백 분석 요청] ${fb.content}`;
    input.focus();

    showToast('피드백이 브릿지 입력창에 추가되었습니다.', 'success');
}

// ==================== BRIDGE ====================

let bridgeConnected = false;

/**
 * Initialize bridge
 */
function initBridge() {
    const form = document.getElementById('bridge-form');
    const input = document.getElementById('bridge-input');
    const clearBtn = document.getElementById('clear-chat-btn');

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const text = input.value.trim();
        if (!text) return;

        if (!bridgeConnected) {
            addBridgeMessage('브릿지에 연결되어 있지 않습니다. 재연결 중...', 'system');
            await connectBridge();
            if (!bridgeConnected) {
                addBridgeMessage('브릿지 연결 실패. 페이지를 새로고침 해주세요.', 'system');
                return;
            }
        }

        addBridgeMessage(text, 'user');
        input.value = '';

        // Show processing indicator
        const typingId = addBridgeTyping();

        // Send command
        bridgeClient.sendCommand(text);
    });

    clearBtn.addEventListener('click', () => {
        const messages = document.getElementById('bridge-messages');
        messages.innerHTML = `
            <div class="chat-welcome">
                <div class="welcome-icon">
                    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                        <path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/>
                    </svg>
                </div>
                <h4>Claude Code 브릿지에 오신 것을 환영합니다</h4>
                <p>서버의 Claude Code CLI와 실시간으로 대화할 수 있습니다.</p>
            </div>
        `;
    });
}

/**
 * Connect to bridge
 */
async function connectBridge() {
    try {
        updateBridgeStatus('processing', '연결 중...');

        bridgeClient.on('status', (payload) => {
            if (payload.status === 'connected') {
                bridgeConnected = true;
                updateBridgeStatus('connected', '연결됨');
                updateBridgeInfo(payload);
            }
        });

        bridgeClient.on('stream', (payload) => {
            updateBridgeTyping(payload.message || '처리 중...');
        });

        bridgeClient.on('response', (payload) => {
            removeBridgeTyping();
            addBridgeMessage(payload.result || payload.message || '응답을 받지 못했습니다.', 'assistant');
        });

        bridgeClient.on('error', (payload) => {
            removeBridgeTyping();
            addBridgeMessage('오류: ' + (payload.message || '알 수 없는 오류'), 'system');
        });

        bridgeClient.on('disconnected', () => {
            bridgeConnected = false;
            updateBridgeStatus('disconnected', '연결 안됨');
        });

        await bridgeClient.connect();
        bridgeConnected = true;

    } catch (error) {
        console.error('Bridge connection failed:', error);
        updateBridgeStatus('disconnected', '연결 실패');
        bridgeConnected = false;
    }
}

/**
 * Update bridge status indicator
 */
function updateBridgeStatus(status, text) {
    const indicator = document.getElementById('admin-connection-status');
    const bridgeIndicator = document.getElementById('bridge-status-card').querySelector('.status-indicator');
    const bridgeText = document.getElementById('bridge-status-text');

    indicator.className = `status-indicator status-${status}`;
    indicator.querySelector('.status-text').textContent = text;

    if (bridgeIndicator) {
        bridgeIndicator.className = `status-indicator status-${status}`;
        bridgeText.textContent = text;
    }
}

/**
 * Update bridge info
 */
function updateBridgeInfo(payload) {
    document.getElementById('bridge-team').textContent = payload.team || '-';
    document.getElementById('bridge-role').textContent = getRoleName(payload.user?.split('@')[0]) || '-';
    document.getElementById('bridge-session').textContent = payload.session_id?.substring(0, 8) || '-';
}

/**
 * Add message to bridge chat
 * Uses DOM API instead of innerHTML for XSS prevention
 */
function addBridgeMessage(text, type) {
    const messages = document.getElementById('bridge-messages');
    const welcome = messages.querySelector('.chat-welcome');
    if (welcome) welcome.remove();

    const msg = document.createElement('div');
    msg.className = `chat-message ${type}`;

    // Create content div using DOM API (XSS safe)
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.textContent = text;  // textContent is XSS-safe
    contentDiv.style.whiteSpace = 'pre-wrap';  // Preserve line breaks

    // Create time div
    const timeDiv = document.createElement('div');
    timeDiv.className = 'message-time';
    timeDiv.textContent = new Date().toLocaleTimeString();

    msg.appendChild(contentDiv);
    msg.appendChild(timeDiv);
    messages.appendChild(msg);
    messages.scrollTop = messages.scrollHeight;
}

let currentTypingEl = null;

/**
 * Add typing indicator
 */
function addBridgeTyping() {
    const messages = document.getElementById('bridge-messages');

    currentTypingEl = document.createElement('div');
    currentTypingEl.className = 'chat-message assistant';
    currentTypingEl.innerHTML = `
        <div class="message-content" style="opacity: 0.7;">처리 중...</div>
    `;
    messages.appendChild(currentTypingEl);
    messages.scrollTop = messages.scrollHeight;
}

/**
 * Update typing indicator
 */
function updateBridgeTyping(text) {
    if (currentTypingEl) {
        currentTypingEl.querySelector('.message-content').textContent = text;
    }
}

/**
 * Remove typing indicator
 */
function removeBridgeTyping() {
    if (currentTypingEl) {
        currentTypingEl.remove();
        currentTypingEl = null;
    }
}

// ==================== AGENTS ====================

/**
 * Initialize agents
 */
function initAgents() {
    // Refresh button
    const refreshBtn = document.getElementById('refresh-agents-btn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', loadAgents);
    }
}

/**
 * Load agents list
 */
async function loadAgents() {
    const grid = document.getElementById('agents-grid');
    if (!grid) return;

    // Show loading
    grid.innerHTML = `
        <div class="loading-state" style="grid-column: 1/-1; text-align: center; padding: 2rem;">
            <div class="spinner"></div>
            <p>에이전트 로딩 중...</p>
        </div>
    `;

    try {
        const response = await authManager.apiRequest('/api/agents');
        if (response.ok) {
            adminState.agents = await response.json();
            renderAgents();
        } else {
            throw new Error('Failed to load agents');
        }
    } catch (error) {
        console.error('Failed to load agents:', error);
        grid.innerHTML = `
            <div class="empty-state" style="grid-column: 1/-1; text-align: center; padding: 2rem;">
                <p>에이전트를 불러오지 못했습니다.</p>
                <button class="btn btn-secondary" onclick="loadAgents()">다시 시도</button>
            </div>
        `;
    }
}

/**
 * Render agents grid
 */
function renderAgents() {
    const grid = document.getElementById('agents-grid');
    if (!grid) return;

    if (adminState.agents.length === 0) {
        grid.innerHTML = `
            <div class="empty-state" style="grid-column: 1/-1; text-align: center; padding: 2rem;">
                <svg class="empty-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="width: 48px; height: 48px; margin-bottom: 1rem;">
                    <path d="M12 6v6m0 0v6m0-6h6m-6 0H6"/>
                </svg>
                <p>등록된 에이전트가 없습니다.</p>
            </div>
        `;
        return;
    }

    grid.innerHTML = adminState.agents.map(agent => {
        const isRunning = adminState.agentRunning.has(agent.name);
        const statusClass = agent.status === 'running' ? 'status-active' :
                           agent.status === 'error' ? 'status-error' : 'status-inactive';
        const statusText = agent.status === 'running' ? '실행 중' :
                          agent.status === 'error' ? '오류' : '대기';

        return `
            <div class="agent-card" data-agent="${escapeHtml(agent.name)}">
                <div class="agent-header">
                    <div class="agent-icon">
                        ${getAgentIcon(agent.name)}
                    </div>
                    <div class="agent-info">
                        <h4 class="agent-name">${escapeHtml(agent.name)}</h4>
                        <span class="agent-version">v${escapeHtml(agent.version || '1.0.0')}</span>
                    </div>
                    <span class="status-tag ${statusClass}">
                        <span class="status-dot"></span>
                        ${statusText}
                    </span>
                </div>
                <p class="agent-description">${escapeHtml(agent.description || '설명 없음')}</p>
                <div class="agent-actions">
                    <button class="btn btn-primary btn-sm" onclick="runAgent('${escapeHtml(agent.name)}')" ${isRunning ? 'disabled' : ''}>
                        ${isRunning ? '실행 중...' : '실행'}
                    </button>
                    <button class="btn btn-secondary btn-sm" onclick="showAgentStatus('${escapeHtml(agent.name)}')">
                        상태
                    </button>
                    <button class="btn btn-secondary btn-sm" onclick="showAgentHelp('${escapeHtml(agent.name)}')">
                        도움말
                    </button>
                </div>
            </div>
        `;
    }).join('');
}

/**
 * Get agent icon based on name
 */
function getAgentIcon(name) {
    const icons = {
        'vacation': `<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/>
        </svg>`,
        'news': `<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 13a2 2 0 002-2V9a2 2 0 00-2-2h-2m-4-3H9M7 16h6M7 8h6v4H7V8z"/>
        </svg>`,
        'pm': `<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01"/>
        </svg>`,
        'system': `<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/>
            <circle cx="12" cy="12" r="3"/>
        </svg>`
    };

    return icons[name.toLowerCase()] || `<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/>
    </svg>`;
}

/**
 * Run agent
 */
async function runAgent(agentName, command = null) {
    if (adminState.agentRunning.has(agentName)) {
        showToast('이 에이전트가 이미 실행 중입니다.', 'warning');
        return;
    }

    const cmd = command || prompt(`${agentName} 에이전트에 전달할 명령어를 입력하세요:`, 'status');
    if (cmd === null) return;

    adminState.agentRunning.add(agentName);
    renderAgents();

    try {
        const response = await authManager.apiRequest(`/api/agents/${agentName}/run`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ command: cmd })
        });

        if (response.ok) {
            const result = await response.json();
            showToast(`${agentName} 에이전트 실행 완료`, 'success');

            // Show result in modal
            showAgentResult(agentName, cmd, result);
        } else {
            const error = await response.json();
            throw new Error(error.detail || 'Agent run failed');
        }
    } catch (error) {
        console.error('Agent run failed:', error);
        showToast(`에이전트 실행 실패: ${error.message}`, 'error');
    } finally {
        adminState.agentRunning.delete(agentName);
        renderAgents();
    }
}

/**
 * Show agent status
 */
async function showAgentStatus(agentName) {
    try {
        const response = await authManager.apiRequest(`/api/agents/${agentName}`);
        if (response.ok) {
            const status = await response.json();
            showAgentResult(agentName, 'status', status);
        }
    } catch (error) {
        showToast('상태 조회 실패', 'error');
    }
}

/**
 * Show agent help
 */
async function showAgentHelp(agentName) {
    await runAgent(agentName, 'help');
}

/**
 * Show agent result in modal
 */
function showAgentResult(agentName, command, result) {
    const modal = document.getElementById('agent-result-modal');
    if (!modal) {
        // Create modal if not exists
        const modalHtml = `
            <div id="agent-result-modal" class="modal-overlay">
                <div class="modal" style="max-width: 600px;">
                    <div class="modal-header">
                        <h3 id="agent-result-title">에이전트 결과</h3>
                        <button class="close-btn" onclick="closeAgentResultModal()">&times;</button>
                    </div>
                    <div class="modal-body" id="agent-result-body">
                    </div>
                    <div class="modal-footer">
                        <button class="btn btn-secondary" onclick="closeAgentResultModal()">닫기</button>
                    </div>
                </div>
            </div>
        `;
        document.body.insertAdjacentHTML('beforeend', modalHtml);
    }

    document.getElementById('agent-result-title').textContent = `${agentName} - ${command}`;

    const body = document.getElementById('agent-result-body');
    body.innerHTML = '';

    const pre = document.createElement('pre');
    pre.style.cssText = 'background: var(--bg-secondary); padding: 1rem; border-radius: 8px; overflow: auto; max-height: 400px;';
    pre.textContent = JSON.stringify(result, null, 2);
    body.appendChild(pre);

    document.getElementById('agent-result-modal').classList.add('visible');
}

/**
 * Close agent result modal
 */
function closeAgentResultModal() {
    const modal = document.getElementById('agent-result-modal');
    if (modal) {
        modal.classList.remove('visible');
    }
}

// ==================== SCHEDULES ====================

/**
 * Initialize schedules
 */
function initSchedules() {
    // Add schedule button
    const addBtn = document.getElementById('add-schedule-btn');
    if (addBtn) {
        addBtn.addEventListener('click', openAddScheduleModal);
    }

    // Refresh button
    const refreshBtn = document.getElementById('refresh-schedules-btn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', loadSchedules);
    }
}

/**
 * Load schedules list
 */
async function loadSchedules() {
    const tbody = document.getElementById('schedules-table-body');
    if (!tbody) return;

    // Show loading
    tbody.innerHTML = `
        <tr class="loading-row">
            <td colspan="6" style="text-align: center;">
                <div class="spinner" style="display: inline-block;"></div>
                스케줄 로딩 중...
            </td>
        </tr>
    `;

    try {
        const response = await authManager.apiRequest('/api/schedules');
        if (response.ok) {
            adminState.schedules = await response.json();
            renderSchedules();
        } else {
            throw new Error('Failed to load schedules');
        }
    } catch (error) {
        console.error('Failed to load schedules:', error);
        tbody.innerHTML = `
            <tr>
                <td colspan="6" style="text-align: center;">
                    스케줄을 불러오지 못했습니다.
                    <button class="btn btn-secondary btn-sm" onclick="loadSchedules()">다시 시도</button>
                </td>
            </tr>
        `;
    }
}

/**
 * Render schedules table
 */
function renderSchedules() {
    const tbody = document.getElementById('schedules-table-body');
    if (!tbody) return;

    if (adminState.schedules.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="6" style="text-align: center; padding: 2rem;">
                    등록된 스케줄이 없습니다.
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = adminState.schedules.map(schedule => {
        const statusClass = schedule.is_enabled ? 'status-active' : 'status-inactive';
        const statusText = schedule.is_enabled ? '활성' : '비활성';

        return `
            <tr data-schedule-id="${schedule.id}">
                <td><strong>${escapeHtml(schedule.name)}</strong></td>
                <td>${escapeHtml(schedule.agent_name)}</td>
                <td><code>${escapeHtml(formatScheduleType(schedule))}</code></td>
                <td>${schedule.last_run ? formatDate(schedule.last_run) : '-'}</td>
                <td>
                    <span class="status-tag ${statusClass}">
                        <span class="status-dot"></span>
                        ${statusText}
                    </span>
                </td>
                <td>
                    <button class="action-btn" onclick="toggleSchedule(${schedule.id}, ${!schedule.is_enabled})" title="${schedule.is_enabled ? '비활성화' : '활성화'}">
                        ${schedule.is_enabled ?
                            '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10 9v6m4-6v6m7-3a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>' :
                            '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"/><path d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>'
                        }
                    </button>
                    <button class="action-btn" onclick="runScheduleNow(${schedule.id})" title="지금 실행">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M13 10V3L4 14h7v7l9-11h-7z"/>
                        </svg>
                    </button>
                    <button class="action-btn" onclick="editSchedule(${schedule.id})" title="편집">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/>
                            <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/>
                        </svg>
                    </button>
                    <button class="action-btn" onclick="deleteSchedule(${schedule.id})" title="삭제">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
                        </svg>
                    </button>
                </td>
            </tr>
        `;
    }).join('');
}

/**
 * Format schedule type for display
 */
function formatScheduleType(schedule) {
    if (schedule.schedule_type === 'cron' && schedule.cron_expression) {
        return `cron: ${schedule.cron_expression}`;
    } else if (schedule.schedule_type === 'interval') {
        const parts = [];
        if (schedule.interval_hours) parts.push(`${schedule.interval_hours}시간`);
        if (schedule.interval_minutes) parts.push(`${schedule.interval_minutes}분`);
        return `interval: ${parts.join(' ')}`;
    } else if (schedule.schedule_type === 'date' && schedule.run_date) {
        return `date: ${formatDate(schedule.run_date)}`;
    }
    return schedule.schedule_type;
}

/**
 * Open add schedule modal
 */
function openAddScheduleModal() {
    const modal = document.getElementById('schedule-modal');
    if (!modal) {
        createScheduleModal();
    }

    // Reset form
    document.getElementById('schedule-form').reset();
    document.getElementById('schedule-id').value = '';
    document.getElementById('schedule-modal-title').textContent = '새 스케줄 추가';

    // Populate agent select
    populateAgentSelect();

    document.getElementById('schedule-modal').classList.add('visible');
}

/**
 * Create schedule modal
 */
function createScheduleModal() {
    const modalHtml = `
        <div id="schedule-modal" class="modal-overlay">
            <div class="modal" style="max-width: 500px;">
                <div class="modal-header">
                    <h3 id="schedule-modal-title">새 스케줄 추가</h3>
                    <button class="close-btn" onclick="closeScheduleModal()">&times;</button>
                </div>
                <form id="schedule-form" onsubmit="saveSchedule(event)">
                    <input type="hidden" id="schedule-id">
                    <div class="modal-body">
                        <div class="form-group">
                            <label for="schedule-name">스케줄 이름</label>
                            <input type="text" id="schedule-name" class="form-input" required placeholder="예: 매일 휴가 동기화">
                        </div>
                        <div class="form-group">
                            <label for="schedule-agent">에이전트</label>
                            <select id="schedule-agent" class="filter-select" required>
                                <option value="">에이전트 선택</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label for="schedule-command">명령어</label>
                            <input type="text" id="schedule-command" class="form-input" placeholder="예: full 3">
                        </div>
                        <div class="form-group">
                            <label for="schedule-type">스케줄 유형</label>
                            <select id="schedule-type" class="filter-select" required onchange="toggleScheduleTypeFields()">
                                <option value="cron">Cron 표현식</option>
                                <option value="interval">간격</option>
                                <option value="date">특정 일시</option>
                            </select>
                        </div>
                        <div id="cron-fields" class="form-group">
                            <label for="schedule-cron">Cron 표현식</label>
                            <input type="text" id="schedule-cron" class="form-input" placeholder="0 9 * * * (매일 9시)">
                            <small style="color: var(--text-muted);">분 시 일 월 요일 형식</small>
                        </div>
                        <div id="interval-fields" class="form-group" style="display: none;">
                            <label>간격</label>
                            <div style="display: flex; gap: 1rem;">
                                <input type="number" id="schedule-hours" class="form-input" placeholder="시간" min="0">
                                <input type="number" id="schedule-minutes" class="form-input" placeholder="분" min="0" max="59">
                            </div>
                        </div>
                        <div id="date-fields" class="form-group" style="display: none;">
                            <label for="schedule-date">실행 일시</label>
                            <input type="datetime-local" id="schedule-date" class="form-input">
                        </div>
                        <div class="form-group">
                            <label class="checkbox-label">
                                <input type="checkbox" id="schedule-active" checked>
                                활성화
                            </label>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" onclick="closeScheduleModal()">취소</button>
                        <button type="submit" class="btn btn-primary">저장</button>
                    </div>
                </form>
            </div>
        </div>
    `;
    document.body.insertAdjacentHTML('beforeend', modalHtml);
}

/**
 * Toggle schedule type fields
 */
function toggleScheduleTypeFields() {
    const type = document.getElementById('schedule-type').value;

    document.getElementById('cron-fields').style.display = type === 'cron' ? 'block' : 'none';
    document.getElementById('interval-fields').style.display = type === 'interval' ? 'block' : 'none';
    document.getElementById('date-fields').style.display = type === 'date' ? 'block' : 'none';
}

/**
 * Populate agent select
 */
function populateAgentSelect() {
    const select = document.getElementById('schedule-agent');
    if (!select) return;

    select.innerHTML = '<option value="">에이전트 선택</option>' +
        adminState.agents.map(agent =>
            `<option value="${escapeHtml(agent.name)}">${escapeHtml(agent.name)}</option>`
        ).join('');
}

/**
 * Close schedule modal
 */
function closeScheduleModal() {
    const modal = document.getElementById('schedule-modal');
    if (modal) {
        modal.classList.remove('visible');
    }
}

/**
 * Save schedule
 */
async function saveSchedule(event) {
    event.preventDefault();

    const id = document.getElementById('schedule-id').value;
    const type = document.getElementById('schedule-type').value;

    const data = {
        name: document.getElementById('schedule-name').value,
        agent_name: document.getElementById('schedule-agent').value,
        command: document.getElementById('schedule-command').value || null,
        schedule_type: type,
        is_enabled: document.getElementById('schedule-active').checked
    };

    if (type === 'cron') {
        data.cron_expression = document.getElementById('schedule-cron').value;
    } else if (type === 'interval') {
        data.interval_hours = parseInt(document.getElementById('schedule-hours').value) || 0;
        data.interval_minutes = parseInt(document.getElementById('schedule-minutes').value) || 0;
    } else if (type === 'date') {
        data.run_date = document.getElementById('schedule-date').value;
    }

    try {
        const url = id ? `/api/schedules/${id}` : '/api/schedules';
        const method = id ? 'PUT' : 'POST';

        const response = await authManager.apiRequest(url, {
            method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });

        if (response.ok) {
            showToast(id ? '스케줄이 수정되었습니다.' : '스케줄이 생성되었습니다.', 'success');
            closeScheduleModal();
            await loadSchedules();
        } else {
            const error = await response.json();
            throw new Error(error.detail || 'Save failed');
        }
    } catch (error) {
        showToast(`저장 실패: ${error.message}`, 'error');
    }
}

/**
 * Edit schedule
 */
async function editSchedule(id) {
    const schedule = adminState.schedules.find(s => s.id === id);
    if (!schedule) return;

    openAddScheduleModal();

    document.getElementById('schedule-modal-title').textContent = '스케줄 편집';
    document.getElementById('schedule-id').value = schedule.id;
    document.getElementById('schedule-name').value = schedule.name;
    document.getElementById('schedule-agent').value = schedule.agent_name;
    document.getElementById('schedule-command').value = schedule.command || '';
    document.getElementById('schedule-type').value = schedule.schedule_type;
    document.getElementById('schedule-active').checked = schedule.is_enabled;

    toggleScheduleTypeFields();

    if (schedule.schedule_type === 'cron') {
        document.getElementById('schedule-cron').value = schedule.cron_expression || '';
    } else if (schedule.schedule_type === 'interval') {
        document.getElementById('schedule-hours').value = schedule.interval_hours || '';
        document.getElementById('schedule-minutes').value = schedule.interval_minutes || '';
    } else if (schedule.schedule_type === 'date') {
        document.getElementById('schedule-date').value = schedule.run_date || '';
    }
}

/**
 * Toggle schedule active status
 */
async function toggleSchedule(id, isEnabled) {
    try {
        const response = await authManager.apiRequest(`/api/schedules/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ is_enabled: isEnabled })
        });

        if (response.ok) {
            showToast(isEnabled ? '스케줄이 활성화되었습니다.' : '스케줄이 비활성화되었습니다.', 'success');
            await loadSchedules();
        }
    } catch (error) {
        showToast('상태 변경 실패', 'error');
    }
}

/**
 * Run schedule now
 */
async function runScheduleNow(id) {
    if (!confirm('이 스케줄을 지금 실행하시겠습니까?')) return;

    try {
        const response = await authManager.apiRequest(`/api/schedules/${id}/run`, {
            method: 'POST'
        });

        if (response.ok) {
            const result = await response.json();
            showToast('스케줄이 실행되었습니다.', 'success');
            await loadSchedules();
        } else {
            throw new Error('Run failed');
        }
    } catch (error) {
        showToast('실행 실패', 'error');
    }
}

/**
 * Delete schedule
 */
async function deleteSchedule(id) {
    if (!confirm('이 스케줄을 삭제하시겠습니까?')) return;

    try {
        const response = await authManager.apiRequest(`/api/schedules/${id}`, {
            method: 'DELETE'
        });

        if (response.ok) {
            showToast('스케줄이 삭제되었습니다.', 'success');
            await loadSchedules();
        }
    } catch (error) {
        showToast('삭제 실패', 'error');
    }
}

// ==================== UTILITIES ====================

/**
 * Get role display name
 */
function getRoleName(role) {
    const roles = {
        'super_admin': '시스템 관리자',
        'team_admin': '팀 관리자',
        'member': '팀원'
    };
    return roles[role] || role;
}

/**
 * Get status display name
 */
function getStatusName(status) {
    const statuses = {
        'new': '신규',
        'reviewing': '검토중',
        'resolved': '해결됨'
    };
    return statuses[status] || status;
}

/**
 * Format date
 */
function formatDate(dateStr) {
    if (!dateStr) return '-';
    const date = new Date(dateStr);
    return date.toLocaleDateString('ko-KR', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit'
    });
}

/**
 * Escape HTML
 */
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Show toast notification
 */
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;

    container.appendChild(toast);

    setTimeout(() => {
        toast.style.animation = 'slideIn 200ms ease reverse';
        setTimeout(() => toast.remove(), 200);
    }, 3000);
}
